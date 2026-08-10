package com.safeher.app.services.ai

import timber.log.Timber

/** Structured diagnostics for the hybrid audio pipeline (no raw PCM unless opted in). */
object AiDetectionLogger {

    fun logFrame(
        rawConfidence: Double,
        rollingAverage: Double?,
        assessment: AudioRiskAssessment?,
        modelVersion: String,
    ) {
        Timber.d(
            "AI audio frame model=%s raw=%.1f rolling=%s risk=%s volSpike=%s freqAbn=%s dur=%.1fs impulsive=%s rms=%.4f zcr=%.3f pitch=%.0fHz centroid=%.0fHz",
            modelVersion,
            rawConfidence,
            rollingAverage?.let { "%.1f".format(it) } ?: "n/a",
            assessment?.riskLevel?.name ?: "n/a",
            assessment?.volumeSpike ?: false,
            assessment?.frequencyAbnormal ?: false,
            assessment?.durationSeconds ?: 0.0,
            assessment?.impulsiveNoise ?: false,
            assessment?.features?.rmsEnergy ?: 0.0,
            assessment?.features?.zeroCrossingRate ?: 0.0,
            assessment?.features?.dominantFrequencyHz ?: 0.0,
            assessment?.features?.spectralCentroidHz ?: 0.0,
        )
    }

    fun logBackendQuery(smoothedScore: Float, action: String?) {
        Timber.i("AI backend /confidence smoothed=%.1f action=%s", smoothedScore, action ?: "pending")
    }

    fun logUserConfirmation(confirmedEmergency: Boolean, uploadQueued: Boolean) {
        Timber.i("AI user confirmation emergency=%s uploadQueued=%s", confirmedEmergency, uploadQueued)
    }

    fun logCooldown(untilMs: Long) {
        Timber.d("AI detection cooldown until=%d", untilMs)
    }
}
