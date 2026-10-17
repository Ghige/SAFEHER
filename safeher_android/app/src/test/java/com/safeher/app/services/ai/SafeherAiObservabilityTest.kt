package com.safeher.app.services.ai

import com.safeher.app.services.AiSensorState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage 3A: observability contract only. Does not prove on-device TFLite.
 */
class SafeherAiObservabilityTest {

    @Test
    fun liveTag_isStableSafeherAi() {
        assertEquals("SAFEHER_AI", AiDetectionLogger.LIVE_TAG)
    }

    @Test
    fun windowCreate_recordsSequenceWithoutRequiringInference() {
        val state = AiSensorState()
        assertEquals(1L, state.nextWindowSequence())
        state.updateAudioBuffer(ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES))
        val window = state.pollCompletedWindow()!!
        assertEquals(1L, window.sequence)
        assertEquals(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES, window.sampleCount)
        assertEquals(CompletedAudioWindow.PRODUCTION_SAMPLE_RATE_HZ, window.sampleRateHz)
        assertTrue(window.isProductionShape)
        assertEquals(2L, state.nextWindowSequence())
        assertTrue(state.pollCompletedWindow() == null)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }
}
