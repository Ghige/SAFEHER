package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Test

class AiFeedbackClassifierTest {

    @Test
    fun cancelMapsToHardNegativeCandidate() {
        assertEquals("CANCELLED", AiFeedbackClassifier.userFeedback(false, false))
        assertEquals("NO_ALERT", AiFeedbackClassifier.outcome(false))
        assertEquals(
            "AI_FALSE_POSITIVE_CANDIDATE",
            AiFeedbackClassifier.candidateCategory(false, false),
        )
    }

    @Test
    fun confirmMapsToDistressCandidate() {
        assertEquals("CONFIRMED_EMERGENCY", AiFeedbackClassifier.userFeedback(true, false))
        assertEquals("MANUAL_SOS_OPENED", AiFeedbackClassifier.outcome(true))
        assertEquals(
            "USER_CONFIRMED_DISTRESS",
            AiFeedbackClassifier.candidateCategory(true, false),
        )
    }

    @Test
    fun timeoutStaysUnreviewed() {
        assertEquals("TIMEOUT", AiFeedbackClassifier.userFeedback(null, true))
        assertEquals("UNREVIEWED", AiFeedbackClassifier.candidateCategory(null, true))
    }

    @Test
    fun fireActionIsEmergencyState() {
        assertEquals("EMERGENCY", AiFeedbackClassifier.predictionState(DecisionContract.ACTION_FIRE))
        assertEquals("SUSPICIOUS", AiFeedbackClassifier.predictionState(DecisionContract.ACTION_CONFIRM))
    }
}
