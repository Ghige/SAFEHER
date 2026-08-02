package com.safeher.app.domain.model

data class AiConfidenceResult(
    val totalScore: Double,
    val action: AiAction,
    val activateGpsStream: Boolean,
    val audioScore: Double,
    val movementScore: Double,
    val heartRateSpike: Boolean,
    val isNight: Boolean?,
    val isIsolated: Boolean,
)

enum class AiAction {
    NOTHING,
    SILENT_VIBRATION,
    CONFIRM_30S,
    FIRE_IMMEDIATELY,
    ;

    companion object {
        fun fromBackend(value: String): AiAction = when (value) {
            "silent_vibration" -> SILENT_VIBRATION
            "confirm_30s" -> CONFIRM_30S
            "fire_immediately" -> FIRE_IMMEDIATELY
            else -> NOTHING
        }
    }
}

data class AiSosResult(
    val fusion: AiConfidenceResult?,
    val alertId: String?,
    val triggerError: String?,
    val reason: String?,
)

data class SensorScores(
    val audioScore: Double?,
    val movementScore: Double?,
    val fallDetected: Boolean = false,
) {
    val hasAnyScore: Boolean
        get() = audioScore != null || movementScore != null
}

enum class AiTriggerSource {
    AUDIO,
    MOVEMENT,
}
