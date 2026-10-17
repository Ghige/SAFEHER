package com.safeher.app.services.ai

/**
 * One completed capture hop for the production audio model.
 *
 * The on-device TFLite input remains 1 second / 16 kHz / mono. This type records
 * sequence and wall-clock metadata so scoring cadence can be verified without
 * logging PCM.
 */
data class CompletedAudioWindow(
    val sequence: Long,
    val timestampMs: Long,
    val sampleCount: Int,
    val sampleRateHz: Int,
    val samples: ShortArray,
) {
    val durationSeconds: Double
        get() = if (sampleRateHz <= 0) 0.0 else sampleCount.toDouble() / sampleRateHz.toDouble()

    val isProductionShape: Boolean
        get() = sampleCount == PRODUCTION_WINDOW_SAMPLES &&
            sampleRateHz == PRODUCTION_SAMPLE_RATE_HZ

    companion object {
        const val PRODUCTION_SAMPLE_RATE_HZ = 16_000
        const val PRODUCTION_WINDOW_SAMPLES = 16_000
        const val PRODUCTION_DURATION_SECONDS = 1.0
    }
}
