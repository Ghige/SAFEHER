package com.safeher.app.services.ai

enum class TemporalState {
    NONE,
    WATCH,
    SUSTAINED,
}

/**
 * Result of the multi-window distress layer. A single high score is WATCH, not SUSTAINED.
 */
data class TemporalDecision(
    val state: TemporalState,
    val consecutiveHot: Int,
    val hotInWindow: Int,
    val windowSize: Int,
    val maxScoreInHorizon: Double,
    val horizonSeconds: Double,
    val threshold: Double,
    val episodeId: Long?,
    val consecutiveSatisfied: Boolean,
    val nOfMSatisfied: Boolean,
    val reason: String,
) {
    val isSustained: Boolean get() = state == TemporalState.SUSTAINED

    companion object {
        fun none(threshold: Double, horizonSeconds: Double): TemporalDecision = TemporalDecision(
            state = TemporalState.NONE,
            consecutiveHot = 0,
            hotInWindow = 0,
            windowSize = 0,
            maxScoreInHorizon = 0.0,
            horizonSeconds = horizonSeconds,
            threshold = threshold,
            episodeId = null,
            consecutiveSatisfied = false,
            nOfMSatisfied = false,
            reason = "empty",
        )
    }
}
