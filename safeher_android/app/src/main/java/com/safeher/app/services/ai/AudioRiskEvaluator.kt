package com.safeher.app.services.ai

enum class AudioRiskLevel {
    LOW,
    MEDIUM,
    HIGH,
}

data class AudioRiskAssessment(
    val riskLevel: AudioRiskLevel,
    val rollingAverage: Double,
    val rawConfidence: Double,
    val durationSeconds: Double,
    val volumeSpike: Boolean,
    val frequencyAbnormal: Boolean,
    val sustainedConfidence: Boolean,
    val impulsiveNoise: Boolean,
    val features: AudioFrameFeatures,
    val phraseScore: Double = 0.0,
    val phraseDetected: Boolean = false,
) {
    /**
     * Backend / SDE query when HIGH from sustained distress OR strong emergency phrase.
     * Volume alone never qualifies.
     */
    val shouldQueryBackend: Boolean
        get() = !impulsiveNoise && (
            (riskLevel == AudioRiskLevel.HIGH && sustainedConfidence) ||
                (phraseDetected && phraseScore >= 0.75) ||
                (riskLevel == AudioRiskLevel.HIGH && phraseDetected)
            )
}

/**
 * Combines model confidence, optional phrase score, acoustic features, and temporal
 * smoothing into a risk level.
 *
 * Volume/RMS is a supporting feature only — never sole HIGH/SOS trigger.
 * Quiet emergency phrases can escalate via [phraseScore] without a volume spike.
 */
object AudioRiskEvaluator {

    fun evaluate(
        config: AiDetectionConfig,
        rawConfidence: Double,
        rollingAverage: Double,
        durationSeconds: Double,
        features: AudioFrameFeatures,
        baselineRms: Double,
        baselineCentroid: Double,
        isSingleSpike: Boolean,
        phraseScore: Double = 0.0,
    ): AudioRiskAssessment {
        val volumeSpike = features.rmsEnergy >= config.absoluteVolumeSpikeRms ||
            (baselineRms > 0.01 && features.rmsEnergy >= baselineRms * config.volumeSpikeMultiplier)

        val frequencyAbnormal = kotlin.math.abs(features.spectralCentroidHz - baselineCentroid) >=
            config.frequencyChangeThresholdHz ||
            features.dominantFrequencyHz >= config.screamFrequencyThresholdHz

        val sustainedConfidence = rollingAverage >= config.confidenceThreshold &&
            durationSeconds >= config.minimumDurationSeconds &&
            !isSingleSpike

        val impulsiveNoise = features.zeroCrossingRate >= config.impulsiveZcrThreshold &&
            durationSeconds < config.impulsiveMaxDurationSeconds

        val phraseDetected = phraseScore >= config.phraseScoreMedium
        val strongPhrase = phraseScore >= config.phraseScoreHigh
        val distressSignal = rollingAverage >= config.confidenceThreshold

        // Volume is NOT required for HIGH. Sustained distress model OR phrase+distress.
        val riskLevel = when {
            impulsiveNoise && !strongPhrase -> AudioRiskLevel.LOW
            // Quiet "help me" with high phrase confidence
            strongPhrase && rollingAverage < config.confidenceThreshold * 0.5 ->
                if (durationSeconds >= 1.0) AudioRiskLevel.MEDIUM else AudioRiskLevel.LOW
            strongPhrase && distressSignal -> AudioRiskLevel.HIGH
            sustainedConfidence -> AudioRiskLevel.HIGH
            phraseDetected && rollingAverage >= config.confidenceThreshold * 0.85 -> AudioRiskLevel.MEDIUM
            distressSignal && (frequencyAbnormal || volumeSpike) &&
                durationSeconds >= config.minimumDurationSeconds * 0.6 -> AudioRiskLevel.MEDIUM
            // Loud-only / single weak signals stay LOW
            volumeSpike && !distressSignal && !phraseDetected -> AudioRiskLevel.LOW
            else -> AudioRiskLevel.LOW
        }

        return AudioRiskAssessment(
            riskLevel = riskLevel,
            rollingAverage = rollingAverage,
            rawConfidence = rawConfidence,
            durationSeconds = durationSeconds,
            volumeSpike = volumeSpike,
            frequencyAbnormal = frequencyAbnormal,
            sustainedConfidence = sustainedConfidence,
            impulsiveNoise = impulsiveNoise,
            features = features,
            phraseScore = phraseScore,
            phraseDetected = phraseDetected,
        )
    }
}
