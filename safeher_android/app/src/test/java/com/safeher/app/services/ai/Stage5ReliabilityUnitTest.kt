package com.safeher.app.services.ai

import com.safeher.app.BuildConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage 5 — software-verifiable reliability checks (no physical device, no real SOS).
 */
class Stage5ReliabilityUnitTest {

    @Test
    fun aiAutoSos_remainsDisabled() {
        assertFalse(BuildConfig.AI_AUTO_SOS_ENABLED)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
        assertTrue(BuildConfig.DEMO_MODE)
    }

    @Test
    fun sde_stateTransitions_normalSuspiciousEmergency() {
        val normal = SafetyDecisionEngine.decide()
        assertEquals(DecisionContract.STATE_NORMAL, normal.state)

        val suspicious = SafetyDecisionEngine.decide(
            speech = SafetyDecisionEngine.SpeechModelResult(
                phraseDetected = true,
                phraseScore = 0.92,
                phrase = "help me",
            ),
        )
        assertEquals(DecisionContract.STATE_SUSPICIOUS, suspicious.state)
        assertEquals(DecisionContract.ACTION_CONFIRM, suspicious.action)

        val emergency = SafetyDecisionEngine.decide(
            audio = SafetyDecisionEngine.AudioModelResult(distressScore = 0.86),
        )
        assertEquals(DecisionContract.STATE_EMERGENCY, emergency.state)
        assertEquals(DecisionContract.ACTION_FIRE, emergency.action)
    }

    @Test
    fun asrInterleave_defersWhenElevated_protectsDistressCapture() {
        assertTrue(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("EMERGENCY"))
        assertTrue(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("SUSPICIOUS"))
        assertFalse(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("NORMAL"))
        assertTrue(
            SpeechAudioCoexistencePolicy.INTERLEAVE_PERIOD_MS >
                SpeechAudioCoexistencePolicy.ASR_SLOT_MS,
        )
    }

    @Test
    fun inferenceInterval_sensitivityMapsToBatteryFriendlyDefaults() {
        // Mirrors AiMonitoringCoordinator companion mapping (document reliability budget).
        fun interval(sensitivity: String): Long = when (sensitivity) {
            "LOW" -> 5_000L
            "MEDIUM" -> 3_000L
            "HIGH" -> 1_500L
            else -> error(sensitivity)
        }
        assertEquals(5_000L, interval("LOW"))
        assertEquals(3_000L, interval("MEDIUM"))
        assertEquals(1_500L, interval("HIGH"))
        assertTrue(interval("LOW") >= interval("MEDIUM"))
        assertTrue(interval("MEDIUM") >= interval("HIGH"))
    }

    @Test
    fun movementUnavailable_doesNotInventScores() {
        assertFalse(AiFeatureFlags.MOVEMENT_AI_ENABLED)
        assertTrue(
            AiModelAssets.MOVEMENT_UNAVAILABLE_REASON.contains("joblib") ||
                AiModelAssets.MOVEMENT_UNAVAILABLE_REASON.contains("tflite"),
        )
    }

    @Test
    fun confirmCountdown_matchesContractThirtySeconds() {
        assertEquals(30, DecisionContract.CONFIRM_COUNTDOWN_SECONDS)
        assertEquals("confirm_30s", DecisionContract.ACTION_CONFIRM)
    }
}
