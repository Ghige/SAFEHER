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
) {
    val shouldQueryBackend: Boolean
        get() = riskLevel == AudioRiskLevel.HIGH &&
            sustainedConfidence &&
            !impulsiveNoise
}

/**
 * Combines model confidence, acoustic features, and temporal smoothing into a risk level.
 * Never marks HIGH from a single raw prediction alone.
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

        val signalCount = listOf(
            rollingAverage >= config.confidenceThreshold,
            volumeSpike,
            frequencyAbnormal,
            durationSeconds >= config.minimumDurationSeconds,
        ).count { it }

        val riskLevel = when {
            impulsiveNoise -> AudioRiskLevel.LOW
            sustainedConfidence && signalCount >= 3 -> AudioRiskLevel.HIGH
            signalCount >= 2 && rollingAverage >= config.confidenceThreshold * 0.85 -> AudioRiskLevel.MEDIUM
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
        )
    }
}
