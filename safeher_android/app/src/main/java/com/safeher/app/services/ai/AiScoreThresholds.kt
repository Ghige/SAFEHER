package com.safeher.app.services.ai

/**
 * Score tiers aligned with Stage-3 [DecisionContract] / backend SDE.
 *
 * Android TFLite engines produce 0–100 sensor scores; fusion is authoritative on backend.
 */
object AiScoreThresholds {
    /** Backend / contract silent band (risk_score * 100). */
    const val TIER_SILENT_VIBRATION = DecisionContract.TIER_SILENT_VIBRATION

    /** MEDIUM risk ≈ confirm_30s / SUSPICIOUS. */
    const val TIER_CONFIRM_30S = DecisionContract.TIER_CONFIRM

    /** HIGH risk ≈ fire_immediately / EMERGENCY. */
    const val TIER_IMMEDIATE_SOS = DecisionContract.TIER_IMMEDIATE_SOS

    /** Distress gate medium (0.55 → 55). */
    const val DISTRESS_MEDIUM = 55

    /** Distress gate high (0.70 → 70). */
    const val DISTRESS_HIGH = 70

    /** AI confirmation countdown — matches DecisionContract / confirm_30s. */
    const val CONFIRM_COUNTDOWN_SECONDS = DecisionContract.CONFIRM_COUNTDOWN_SECONDS

    /** Legacy alias — do not treat as fusion fire threshold. */
    @Deprecated("Use TIER_IMMEDIATE_SOS (65) — contract v1.0.0")
    const val SENSOR_NOISE_FLOOR = 55
}
