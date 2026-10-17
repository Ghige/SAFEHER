package com.safeher.app.services.ai

import java.util.ArrayDeque
import kotlin.math.max

object PopupSuppressionReason {
    const val NOT_SUSTAINED = "not_sustained"
    const val POPUP_VISIBLE = "popup_visible"
    const val COOLDOWN = "cooldown"
    const val SAME_EPISODE = "same_episode"
    const val FREQUENCY_LIMIT = "frequency_limit"
}

data class PopupEligibilityResult(
    val eligible: Boolean,
    val suppressionReason: String?,
    val episodeId: Long?,
    val strongerEvent: Boolean,
    /** Popup rules never stop scoring. */
    val inferenceContinues: Boolean = true,
)

/**
 * UI-only eligibility for the confirm-first popup.
 *
 * Cooldown, frequency, visible-popup, and same-episode rules must not stop inference.
 */
class PopupEligibilityController(
    private val config: AiDetectionConfig,
) {
    private var cooldownUntilMs: Long = 0L
    private var lastPopupEpisodeId: Long? = null
    private var lastPopupScore: Double = 0.0
    private var popupVisible: Boolean = false
    private val popupTimestamps = ArrayDeque<Long>()

    val isPopupVisible: Boolean get() = popupVisible
    val lastShownScore: Double get() = lastPopupScore
    val cooldownActiveAt: (Long) -> Boolean get() = { now -> now < cooldownUntilMs }

    fun reset() {
        cooldownUntilMs = 0L
        lastPopupEpisodeId = null
        lastPopupScore = 0.0
        popupVisible = false
        popupTimestamps.clear()
    }

    fun onPopupShown(episodeId: Long?, score: Double, nowMs: Long) {
        popupVisible = true
        lastPopupEpisodeId = episodeId
        lastPopupScore = score
        popupTimestamps.addLast(nowMs)
        prunePopupTimes(nowMs)
    }

    fun onPopupDismissed(nowMs: Long) {
        popupVisible = false
        cooldownUntilMs = nowMs + config.cooldownSeconds * 1_000L
    }

    fun evaluate(
        nowMs: Long,
        temporal: TemporalDecision,
        currentScore: Double,
        popupVisibleOverride: Boolean? = null,
        phraseConfirm: Boolean = false,
        fallConfirm: Boolean = false,
    ): PopupEligibilityResult {
        val visible = popupVisibleOverride ?: popupVisible
        val detectionReady = temporal.isSustained || phraseConfirm || fallConfirm
        val episodeId = temporal.episodeId
        val peak = max(currentScore, temporal.maxScoreInHorizon)
        val stronger = lastPopupScore > 0.0 &&
            peak >= lastPopupScore + config.escalationScoreMargin
        val sameEpisode = episodeId != null && episodeId == lastPopupEpisodeId
        val inCooldown = nowMs < cooldownUntilMs
        prunePopupTimes(nowMs)
        val overFrequency = popupTimestamps.size >= config.maxPopupsPerPeriod

        val reason = when {
            !detectionReady -> PopupSuppressionReason.NOT_SUSTAINED
            visible -> PopupSuppressionReason.POPUP_VISIBLE
            inCooldown && sameEpisode && !stronger -> PopupSuppressionReason.COOLDOWN
            sameEpisode && !stronger -> PopupSuppressionReason.SAME_EPISODE
            overFrequency && !stronger -> PopupSuppressionReason.FREQUENCY_LIMIT
            else -> null
        }

        return PopupEligibilityResult(
            eligible = reason == null,
            suppressionReason = reason,
            episodeId = episodeId,
            strongerEvent = stronger,
            inferenceContinues = true,
        )
    }

    private fun prunePopupTimes(nowMs: Long) {
        val cutoff = nowMs - config.popupFrequencyPeriodSeconds * 1_000L
        while (popupTimestamps.isNotEmpty() && popupTimestamps.first() < cutoff) {
            popupTimestamps.removeFirst()
        }
    }
}
