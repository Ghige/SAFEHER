package com.safeher.app.services

import com.safeher.app.services.ai.CompletedAudioWindow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AiSensorStateWindowTest {

    @Test
    fun completedWindows_areSequencedAndPolledOnce() {
        val state = AiSensorState()
        val first = ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES) { 1 }
        val second = ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES) { 2 }
        state.updateAudioBuffer(first)
        state.updateAudioBuffer(second)

        val a = state.pollCompletedWindow()
        val b = state.pollCompletedWindow()
        assertNotNull(a)
        assertNotNull(b)
        assertEquals(1L, a!!.sequence)
        assertEquals(2L, b!!.sequence)
        assertTrue(a.timestampMs > 0L)
        assertTrue(b.timestampMs >= a.timestampMs)
        assertTrue(a.isProductionShape)
        assertEquals(1.toShort(), a.samples[0])
        assertEquals(2.toShort(), b.samples[0])
        assertNull(state.pollCompletedWindow())
    }

    @Test
    fun pendingQueue_dropsOldestWhenCapped() {
        val state = AiSensorState()
        repeat(AiSensorState.MAX_PENDING_WINDOWS + 2) { index ->
            state.updateAudioBuffer(
                ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES) { index.toShort() },
            )
        }
        assertEquals(AiSensorState.MAX_PENDING_WINDOWS, state.pendingCompletedWindowCount())
        assertEquals(2L, state.droppedCompletedWindowCount())
        val firstKept = state.pollCompletedWindow()
        assertEquals(3L, firstKept!!.sequence)
    }
}
