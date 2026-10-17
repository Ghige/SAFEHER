package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SafetyDecisionEngineTest {

    @Test
    fun quietHelpMe_reachesMediumOrHigh() {
        val d = SafetyDecisionEngine.decide(
            audio = SafetyDecisionEngine.AudioModelResult(distressScore = 0.2, volumeScore = 0.1),
            speech = SafetyDecisionEngine.SpeechModelResult(
                phraseDetected = true,
                phraseScore = 0.95,
                phrase = "help me",
                language = "english",
            ),
        )
        assertTrue(
            d.riskLevel == SafetyDecisionEngine.RiskLevel.MEDIUM ||
                d.riskLevel == SafetyDecisionEngine.RiskLevel.HIGH,
        )
        assertTrue(d.reasonCodes.contains("EMERGENCY_PHRASE"))
    }

    @Test
    fun movementOnly_doesNotTriggerSos() {
        val d = SafetyDecisionEngine.decide(
            movement = SafetyDecisionEngine.MovementModelResult(movementAnomalyScore = 0.95),
        )
        assertFalse(d.shouldTriggerSos)
        assertTrue(d.reasonCodes.contains("MOVEMENT_ONLY_SUPPRESSED"))
    }

    @Test
    fun volumeOnly_staysLow() {
        val d = SafetyDecisionEngine.decide(
            audio = SafetyDecisionEngine.AudioModelResult(distressScore = 0.0, volumeScore = 1.0),
        )
        assertEquals(SafetyDecisionEngine.RiskLevel.LOW, d.riskLevel)
        assertFalse(d.shouldTriggerSos)
    }

    @Test
    fun phraseDetector_matchesHindi() {
        val r = EmergencyPhraseDetector.detect("mujhe bachao")
        assertTrue(r.phraseDetected)
        assertEquals("hindi", r.language)
    }
}
