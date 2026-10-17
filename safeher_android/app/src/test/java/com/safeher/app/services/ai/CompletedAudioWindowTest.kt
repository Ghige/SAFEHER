package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CompletedAudioWindowTest {

    @Test
    fun productionWindow_isOneSecondAt16kHzMono() {
        val window = CompletedAudioWindow(
            sequence = 1L,
            timestampMs = 1_000L,
            sampleCount = CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES,
            sampleRateHz = CompletedAudioWindow.PRODUCTION_SAMPLE_RATE_HZ,
            samples = ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES),
        )
        assertEquals(16_000, window.sampleCount)
        assertEquals(16_000, window.sampleRateHz)
        assertEquals(1.0, window.durationSeconds, 0.0001)
        assertEquals(CompletedAudioWindow.PRODUCTION_DURATION_SECONDS, window.durationSeconds, 0.0001)
        assertTrue(window.isProductionShape)
        assertEquals(window.samples.size, CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES)
    }

    @Test
    fun nonProductionShape_isRejected() {
        val window = CompletedAudioWindow(
            sequence = 2L,
            timestampMs = 2_000L,
            sampleCount = 8_000,
            sampleRateHz = 16_000,
            samples = ShortArray(8_000),
        )
        assertEquals(0.5, window.durationSeconds, 0.0001)
        assertFalse(window.isProductionShape)
    }
}
