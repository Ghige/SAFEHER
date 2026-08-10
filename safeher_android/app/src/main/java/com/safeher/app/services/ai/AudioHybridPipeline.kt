package com.safeher.app.services.ai

import javax.inject.Inject
import javax.inject.Singleton

/**
 * Hybrid on-device audio pipeline:
 * preprocess → TFLite → features → rolling average → risk assessment.
 */
@Singleton
class AudioHybridPipeline @Inject constructor(
    private val audioInferenceEngine: AudioInferenceEngine,
) {
    private val config = AiDetectionConfig()
    private val rollingWindow = RollingConfidenceWindow(config.rollingWindowSize)
    private var baselineRms = 0.05
    private var baselineCentroid = 1_000.0

    val detectionConfig: AiDetectionConfig get() = config

    data class CycleResult(
        val rawConfidence: Double,
        val rollingAverage: Double,
        val assessment: AudioRiskAssessment,
        val audioBuffer: ShortArray,
    )

    suspend fun process(audioBuffer: ShortArray, sampleRate: Int): CycleResult? {
        if (!audioInferenceEngine.isAvailable) return null

        val rawConfidence = audioInferenceEngine.inferDistressScore(audioBuffer, sampleRate) ?: return null
        val features = AudioFeatureExtractor.extract(audioBuffer)
        updateBaselines(features)

        rollingWindow.add(rawConfidence)
        val rollingAverage = rollingWindow.average() ?: rawConfidence
        val durationSeconds = rollingWindow.durationAboveThreshold(config.confidenceThreshold)
        val singleSpike = rollingWindow.isSingleSpike(config.confidenceThreshold)

        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = rawConfidence,
            rollingAverage = rollingAverage,
            durationSeconds = durationSeconds,
            features = features,
            baselineRms = baselineRms,
            baselineCentroid = baselineCentroid,
            isSingleSpike = singleSpike,
        )

        AiDetectionLogger.logFrame(
            rawConfidence = rawConfidence,
            rollingAverage = rollingAverage,
            assessment = assessment,
            modelVersion = AiModelVersion.AUDIO_DISTRESS,
        )

        return CycleResult(
            rawConfidence = rawConfidence,
            rollingAverage = rollingAverage,
            assessment = assessment,
            audioBuffer = audioBuffer,
        )
    }

    fun reset() {
        rollingWindow.clear()
        baselineRms = 0.05
        baselineCentroid = 1_000.0
    }

    private fun updateBaselines(features: AudioFrameFeatures) {
        baselineRms = baselineRms * 0.95 + features.rmsEnergy * 0.05
        baselineCentroid = baselineCentroid * 0.95 + features.spectralCentroidHz * 0.05
    }
}
