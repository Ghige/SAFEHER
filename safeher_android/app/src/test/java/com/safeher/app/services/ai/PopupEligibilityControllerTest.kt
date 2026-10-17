package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PopupEligibilityControllerTest {

    private val config = AiDetectionConfig(
        cooldownSeconds = 60L,
        maxPopupsPerPeriod = 3,
        popupFrequencyPeriodSeconds = 600L,
        escalationScoreMargin = 10.0,
    )

    private fun sustained(episodeId: Long, maxScore: Double = 80.0) = TemporalDecision(
        state = TemporalState.SUSTAINED,
        consecutiveHot = 3,
        hotInWindow = 3,
        windowSize = 3,
        maxScoreInHorizon = maxScore,
        horizonSeconds = 6.0,
        threshold = 75.0,
        episodeId = episodeId,
        consecutiveSatisfied = true,
        nOfMSatisfied = false,
        reason = "test",
    )

    @Test
    fun sustainedDistress_canBecomeEligible() {
        val controller = PopupEligibilityController(config)
        val result = controller.evaluate(
            nowMs = 10_000L,
            temporal = sustained(1L, 82.0),
            currentScore = 82.0,
        )
        assertTrue(result.eligible)
        assertEquals(null, result.suppressionReason)
        assertTrue(result.inferenceContinues)
    }

    @Test
    fun cooldown_suppressesPopup_butInferenceContinues() {
        val controller = PopupEligibilityController(config)
        controller.onPopupShown(episodeId = 1L, score = 80.0, nowMs = 10_000L)
        controller.onPopupDismissed(nowMs = 10_000L)
        val result = controller.evaluate(
            nowMs = 20_000L,
            temporal = sustained(1L, 80.0),
            currentScore = 80.0,
        )
        assertFalse(result.eligible)
        assertEquals(PopupSuppressionReason.COOLDOWN, result.suppressionReason)
        assertTrue(result.inferenceContinues)
        assertFalse(
            ContinuousInferencePolicy.popupUiStopsInference(
                popupVisible = false,
                cooldownActive = true,
                frequencyLimited = false,
            ),
        )
    }

    @Test
    fun popupVisible_doesNotStopInference() {
        val controller = PopupEligibilityController(config)
        controller.onPopupShown(episodeId = 1L, score = 80.0, nowMs = 10_000L)
        val result = controller.evaluate(
            nowMs = 11_000L,
            temporal = sustained(1L, 85.0),
            currentScore = 85.0,
        )
        assertFalse(result.eligible)
        assertEquals(PopupSuppressionReason.POPUP_VISIBLE, result.suppressionReason)
        assertTrue(result.inferenceContinues)
        assertTrue(controller.isPopupVisible)
        assertFalse(
            ContinuousInferencePolicy.popupUiStopsInference(
                popupVisible = true,
                cooldownActive = false,
                frequencyLimited = false,
            ),
        )
    }

    @Test
    fun laterStrongerEvent_regainsEligibilityDuringCooldown() {
        val controller = PopupEligibilityController(config)
        controller.onPopupShown(episodeId = 1L, score = 80.0, nowMs = 10_000L)
        controller.onPopupDismissed(nowMs = 10_000L)
        val result = controller.evaluate(
            nowMs = 20_000L,
            temporal = sustained(1L, 92.0),
            currentScore = 92.0,
        )
        assertTrue(result.strongerEvent)
        assertTrue(result.eligible)
        assertTrue(result.inferenceContinues)
    }

    @Test
    fun frequencyLimit_affectsUiOnly() {
        val controller = PopupEligibilityController(config)
        var now = 0L
        repeat(3) { index ->
            val episode = (index + 1).toLong()
            val shown = controller.evaluate(now, sustained(episode, 80.0), 80.0)
            assertTrue(shown.eligible)
            controller.onPopupShown(episode, 80.0, now)
            controller.onPopupDismissed(now)
            now += 70_000L
        }
        val blocked = controller.evaluate(
            nowMs = now,
            temporal = sustained(4L, 80.0),
            currentScore = 80.0,
        )
        assertFalse(blocked.eligible)
        assertEquals(PopupSuppressionReason.FREQUENCY_LIMIT, blocked.suppressionReason)
        assertTrue(blocked.inferenceContinues)
        assertFalse(
            ContinuousInferencePolicy.popupUiStopsInference(
                popupVisible = false,
                cooldownActive = false,
                frequencyLimited = true,
            ),
        )
    }

    @Test
    fun sameEpisodeAfterCooldown_staysSuppressedWithoutStrongerEvent() {
        val controller = PopupEligibilityController(config)
        controller.onPopupShown(1L, 80.0, 0L)
        controller.onPopupDismissed(0L)
        val later = controller.evaluate(
            nowMs = 120_000L,
            temporal = sustained(1L, 80.0),
            currentScore = 80.0,
        )
        assertFalse(later.eligible)
        assertEquals(PopupSuppressionReason.SAME_EPISODE, later.suppressionReason)
        assertTrue(later.inferenceContinues)
    }
}
