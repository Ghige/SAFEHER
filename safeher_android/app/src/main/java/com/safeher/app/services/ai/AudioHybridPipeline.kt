package com.safeher.app.services.ai

import javax.inject.Inject
import javax.inject.Singleton
import kotlin.system.measureTimeMillis

/**
 * Hybrid on-device pipeline:
 * preprocess → TFLite distress → phrase catalog/ASR → features → rolling → local SDE (DecisionContract).
 *
 * Volume is never the sole SOS trigger. Missing signals stay null/0 — never invented.
 */
@Singleton
class AudioHybridPipeline @Inject constructor(
    private val audioInferenceEngine: AudioInferenceEngine,
    private val speechPhraseInferenceEngine: SpeechPhraseInferenceEngine,
    private val transcriptStore: SpeechTranscriptStore,
) {
    private val config = AiDetectionConfig()
    private val rollingWindow = RollingConfidenceWindow(config.rollingWindowSize)
    private val scoreHistory = ScoreHistory(
        evidenceHorizonSeconds = config.evidenceHorizonSeconds,
        maxSamples = maxOf(
            config.rollingWindowSize,
            kotlin.math.ceil(config.evidenceHorizonSeconds).toInt() + 2,
        ),
    )
    private val sustainedDistressDecider = SustainedDistressDecider(config)
    private var baselineRms = 0.05
    private var baselineCentroid = 1_000.0

    val detectionConfig: AiDetectionConfig get() = config

    data class CycleResult(
        val rawConfidence: Double,
        val rollingAverage: Double,
        val assessment: AudioRiskAssessment,
        val audioBuffer: ShortArray,
        val phraseScore: Double = 0.0,
        val detectedPhrase: String? = null,
        val phraseLanguage: String? = null,
        val safetyDecision: SafetyDecisionEngine.SafetyDecision? = null,
        val audioLatencyMs: Long? = null,
        val pipelineLatencyMs: Long? = null,
        val windowSequence: Long = 0L,
        val windowTimestampMs: Long = 0L,
        val temporalDecision: TemporalDecision? = null,
    )

    /**
     * @param movementScore0to1 optional real movement model output (0–1); null if unavailable
     * @param fallDetected only when movement model reports it
     */
    suspend fun process(
        audioBuffer: ShortArray,
        sampleRate: Int,
        movementScore0to1: Double? = null,
        fallDetected: Boolean = false,
        windowSequence: Long = 0L,
        windowTimestampMs: Long = System.currentTimeMillis(),
    ): CycleResult? {
        if (!audioInferenceEngine.isAvailable) {
            AiDetectionLogger.liveTfliteBefore(
                sequence = windowSequence,
                sampleCount = audioBuffer.size,
            )
            AiDetectionLogger.liveTfliteAfter(
                sequence = windowSequence,
                score = null,
                latencyMs = null,
                error = audioInferenceEngine.lastError ?: "engine_unavailable",
            )
            return null
        }

        var cycle: CycleResult? = null
        val pipelineMs = measureTimeMillis {
            AiDetectionLogger.liveTfliteBefore(
                sequence = windowSequence,
                sampleCount = audioBuffer.size,
            )
            val rawConfidence = audioInferenceEngine.inferDistressScore(audioBuffer, sampleRate)
            AiDetectionLogger.liveTfliteAfter(
                sequence = windowSequence,
                score = rawConfidence,
                latencyMs = audioInferenceEngine.lastLatencyMs,
                error = if (rawConfidence == null) audioInferenceEngine.lastError else null,
            )
            if (rawConfidence == null) return@measureTimeMillis
            val features = AudioFeatureExtractor.extract(audioBuffer)
            updateBaselines(features)

            rollingWindow.add(rawConfidence, timestampMs = windowTimestampMs)
            scoreHistory.add(
                ScoreSample(
                    sequence = windowSequence,
                    timestampMs = windowTimestampMs,
                    score = rawConfidence,
                ),
                nowMs = windowTimestampMs,
            )
            val temporalDecision = sustainedDistressDecider.evaluate(
                history = scoreHistory.snapshot(),
                nowMs = windowTimestampMs,
            )
            AiDetectionLogger.liveTemporal(
                sequence = windowSequence,
                score = rawConfidence,
                state = temporalDecision.state.name,
            )
            val rollingAverage = rollingWindow.average() ?: rawConfidence
            val durationSeconds = rollingWindow.durationAboveThreshold(
                config.confidenceThreshold,
                nowMs = windowTimestampMs,
            )
            val singleSpike = rollingWindow.isSingleSpike(config.confidenceThreshold)

            // Transcript from ASR (when mic free) or inject — never invent phrase scores.
            val phrase = speechPhraseInferenceEngine.inferFromLatestTranscript()
            val volumeScore = (features.rmsEnergy / 0.25).coerceIn(0.0, 1.0)

            val assessment = AudioRiskEvaluator.evaluate(
                config = config,
                rawConfidence = rawConfidence,
                rollingAverage = rollingAverage,
                durationSeconds = durationSeconds,
                features = features,
                baselineRms = baselineRms,
                baselineCentroid = baselineCentroid,
                isSingleSpike = singleSpike,
                phraseScore = phrase.phraseScore,
            )

            val safetyDecision = SafetyDecisionEngine.decide(
                audio = SafetyDecisionEngine.AudioModelResult(
                    distressScore = rollingAverage / 100.0,
                    audioConfidence = rawConfidence / 100.0,
                    volumeScore = volumeScore,
                ),
                speech = SafetyDecisionEngine.SpeechModelResult(
                    phraseDetected = phrase.phraseDetected,
                    phraseScore = phrase.phraseScore,
                    language = phrase.language,
                    phrase = phrase.phrase,
                ),
                movement = SafetyDecisionEngine.MovementModelResult(
                    movementAnomalyScore = movementScore0to1 ?: 0.0,
                    fallDetected = fallDetected,
                ),
            )

            AiDetectionLogger.logAudioWindow(
                sequence = windowSequence,
                timestampMs = windowTimestampMs,
                sampleCount = audioBuffer.size,
                sampleRateHz = sampleRate,
            )
            AiDetectionLogger.logInferenceExecution(
                sequence = windowSequence,
                score = rawConfidence,
                latencyMs = audioInferenceEngine.lastLatencyMs,
            )
            AiDetectionLogger.logTemporalState(temporalDecision)
            AiDetectionLogger.logFrame(
                rawConfidence = rawConfidence,
                rollingAverage = rollingAverage,
                assessment = assessment,
                modelVersion = AiModelVersion.AUDIO_DISTRESS,
            )
            AiDetectionLogger.logLocalDecision(safetyDecision)

            cycle = CycleResult(
                rawConfidence = rawConfidence,
                rollingAverage = rollingAverage,
                assessment = assessment,
                audioBuffer = audioBuffer,
                phraseScore = phrase.phraseScore,
                detectedPhrase = phrase.phrase,
                phraseLanguage = phrase.language,
                safetyDecision = safetyDecision,
                audioLatencyMs = audioInferenceEngine.lastLatencyMs,
                pipelineLatencyMs = null, // filled below
                windowSequence = windowSequence,
                windowTimestampMs = windowTimestampMs,
                temporalDecision = temporalDecision,
            )
        }

        return cycle?.copy(pipelineLatencyMs = pipelineMs)
    }

    fun reset() {
        rollingWindow.clear()
        scoreHistory.clear()
        sustainedDistressDecider.reset()
        baselineRms = 0.05
        baselineCentroid = 1_000.0
        transcriptStore.clear()
    }

    private fun updateBaselines(features: AudioFrameFeatures) {
        baselineRms = baselineRms * 0.95 + features.rmsEnergy * 0.05
        baselineCentroid = baselineCentroid * 0.95 + features.spectralCentroidHz * 0.05
    }
}
