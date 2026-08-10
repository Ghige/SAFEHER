package com.safeher.app.services.ai

/**
 * Score tiers aligned with backend [confidence_scorer.py].
 *
 * Android TFLite engines produce 0–100 sensor scores; fusion tiers are applied server-side.
 * Audio/movement contributions below [SENSOR_NOISE_FLOOR] are ignored by the backend scorer.
 */
object AiScoreThresholds {
    /** Backend ignores audio/movement scores below this (noise floor). */
    const val SENSOR_NOISE_FLOOR = 60

    /** Silent haptic only — low fused confidence. */
    const val TIER_SILENT_VIBRATION = 40

    /** 30 s SOS countdown before auto-trigger. */
    const val TIER_CONFIRM_30S = 60

    /** Immediate SOS + live location stream. */
    const val TIER_IMMEDIATE_SOS = 80

    /** High-confidence audio tier (backend _audio_contribution). */
    const val AUDIO_TIER_HIGH = 75

    /** Very high-confidence audio tier. */
    const val AUDIO_TIER_CRITICAL = 90
}
