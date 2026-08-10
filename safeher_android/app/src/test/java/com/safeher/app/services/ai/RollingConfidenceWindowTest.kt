package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RollingConfidenceWindowTest {

    @Test
    fun average_ignoresBeyondWindowSize() {
        val window = RollingConfidenceWindow(maxSize = 3)
        window.add(80.0, timestampMs = 1_000L)
        window.add(82.0, timestampMs = 2_000L)
        window.add(90.0, timestampMs = 3_000L)
        window.add(88.0, timestampMs = 4_000L)
        assertEquals(3, window.size)
        assertEquals((82.0 + 90.0 + 88.0) / 3.0, window.average()!!, 0.01)
    }

    @Test
    fun isSingleSpike_detectsOutlier() {
        val window = RollingConfidenceWindow(maxSize = 5)
        window.add(70.0)
        window.add(72.0)
        window.add(95.0)
        window.add(71.0)
        assertTrue(window.isSingleSpike(threshold = 75.0))
    }

    @Test
    fun durationAboveThreshold_tracksSustainedSignal() {
        val window = RollingConfidenceWindow(maxSize = 8)
        window.add(60.0, timestampMs = 0L)
        window.add(80.0, timestampMs = 1_000L)
        window.add(82.0, timestampMs = 3_000L)
        window.add(85.0, timestampMs = 6_000L)
        assertEquals(5.0, window.durationAboveThreshold(75.0, nowMs = 6_000L), 0.01)
    }

    @Test
    fun clear_resetsWindow() {
        val window = RollingConfidenceWindow(maxSize = 5)
        window.add(80.0)
        window.clear()
        assertFalse(window.isSingleSpike(75.0))
        assertEquals(null, window.average())
    }
}
