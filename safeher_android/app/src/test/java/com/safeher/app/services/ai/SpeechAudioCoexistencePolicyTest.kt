package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechAudioCoexistencePolicyTest {

    @Test
    fun defersAsrWhenLocalStateElevated() {
        assertTrue(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("SUSPICIOUS"))
        assertTrue(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("EMERGENCY"))
        assertFalse(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState("NORMAL"))
        assertFalse(SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState(null))
    }

    @Test
    fun interleaveTimingIsSane() {
        assertTrue(SpeechAudioCoexistencePolicy.INTERLEAVE_PERIOD_MS > SpeechAudioCoexistencePolicy.ASR_SLOT_MS)
        assertEquals(true, AiFeatureFlags.SPEECH_ASR_INTERLEAVE_ENABLED)
        assertFalse(AiFeatureFlags.MOVEMENT_AI_ENABLED)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }
}
