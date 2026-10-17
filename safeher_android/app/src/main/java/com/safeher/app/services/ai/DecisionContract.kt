package com.safeher.app.services.ai

/**
 * Stage-3 shared decision contract values (mirrors decision_contract.json).
 *
 * Source of truth for packaging: app/src/main/assets/decision_contract.json
 * Unit tests assert these constants match that JSON / golden vectors.
 */
object DecisionContract {
    const val CONTRACT_VERSION = "1.0.0"

    /** Matches API action name and confirmation.countdown_seconds. */
    const val ACTION_CONFIRM = "confirm_30s"
    const val CONFIRM_COUNTDOWN_SECONDS = 30

    const val ACTION_NOTHING = "nothing"
    const val ACTION_SILENT = "silent_vibration"
    const val ACTION_FIRE = "fire_immediately"

    const val STATE_NORMAL = "NORMAL"
    const val STATE_SUSPICIOUS = "SUSPICIOUS"
    const val STATE_EMERGENCY = "EMERGENCY"

    const val WEIGHT_DISTRESS = 0.40
    const val WEIGHT_PHRASE = 0.40
    const val WEIGHT_MOVEMENT = 0.20
    const val WEIGHT_VOLUME = 0.05
    const val MULTI_STRONG_BONUS = 0.12

    const val DISTRESS_MEDIUM = 0.55
    const val DISTRESS_HIGH = 0.70
    const val PHRASE_MEDIUM = 0.55
    const val PHRASE_HIGH = 0.75
    const val MOVE_MEDIUM = 0.60
    const val MOVE_HIGH = 0.80
    const val VOLUME_LOUD = 0.70
    const val DISTRESS_FLOOR_MEDIUM = 0.60
    const val DISTRESS_FLOOR_HIGH = 0.80

    const val RISK_SILENT = 0.20
    const val RISK_MEDIUM = 0.40
    const val RISK_HIGH = 0.65

    /** Display helpers (risk band * 100). */
    const val TIER_SILENT_VIBRATION = 20
    const val TIER_CONFIRM = 40
    const val TIER_IMMEDIATE_SOS = 65

    /** Stage 8 confirm-first beta — keep aligned with decision_contract.json. */
    const val CONFIRM_FIRST_BETA = true
    const val NO_RESPONSE_WHEN_AUTO_SOS_OFF = "DISMISS_SAFE_NO_ALERT"
    const val FALL_BYPASSES_CONFIRM_UI = false
}
