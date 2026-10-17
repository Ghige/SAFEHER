package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AiConfirmFirstPolicyTest {

    @Test
    fun cancelNeverCreatesAlert() {
        val o = AiConfirmFirstPolicy.resolve(
            userConfirmed = false,
            timedOut = false,
            recommendedAction = DecisionContract.ACTION_FIRE,
            autoSosEnabled = false,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.CANCELLED_NO_ALERT, o)
        assertFalse(AiConfirmFirstPolicy.createsAlert(o))
        assertFalse(AiConfirmFirstPolicy.opensManualSosCountdown(o))
    }

    @Test
    fun noResponseWithAutoSosOffDismissesSafely() {
        val o = AiConfirmFirstPolicy.resolve(
            userConfirmed = null,
            timedOut = true,
            recommendedAction = DecisionContract.ACTION_CONFIRM,
            autoSosEnabled = false,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.NO_RESPONSE_DISMISS_SAFE, o)
        assertFalse(AiConfirmFirstPolicy.createsAlert(o))
    }

    @Test
    fun userConfirmOpensManualCountdown() {
        val o = AiConfirmFirstPolicy.resolve(
            userConfirmed = true,
            timedOut = false,
            recommendedAction = DecisionContract.ACTION_CONFIRM,
            autoSosEnabled = false,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_MANUAL_SOS, o)
        assertTrue(AiConfirmFirstPolicy.opensManualSosCountdown(o))
        assertFalse(AiConfirmFirstPolicy.createsAlert(o))
    }

    @Test
    fun promptKindMapsActions() {
        assertEquals(
            AiConfirmFirstPolicy.PromptKind.EMERGENCY,
            AiConfirmFirstPolicy.promptKind(DecisionContract.ACTION_FIRE),
        )
        assertEquals(
            AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
            AiConfirmFirstPolicy.promptKind(DecisionContract.ACTION_CONFIRM),
        )
    }

    @Test
    fun countdownMatchesContract() {
        assertEquals(30, AiConfirmFirstPolicy.countdownSeconds())
        assertEquals(30, DecisionContract.CONFIRM_COUNTDOWN_SECONDS)
        assertTrue(DecisionContract.CONFIRM_FIRST_BETA)
        assertFalse(DecisionContract.FALL_BYPASSES_CONFIRM_UI)
    }
}
