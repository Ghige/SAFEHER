package com.safeher.app.services.ai

import java.util.ArrayDeque

/** Rolling window of raw model confidence scores for temporal smoothing. */
class RollingConfidenceWindow(
    private val maxSize: Int,
) {
    private val samples = ArrayDeque<Sample>()

    data class Sample(val confidence: Double, val timestampMs: Long)

    val size: Int get() = samples.size

    fun add(confidence: Double, timestampMs: Long = System.currentTimeMillis()) {
        while (samples.size >= maxSize) {
            samples.removeFirst()
        }
        samples.addLast(Sample(confidence, timestampMs))
    }

    fun clear() {
        samples.clear()
    }

    fun average(): Double? {
        if (samples.isEmpty()) return null
        return samples.sumOf { it.confidence } / samples.size
    }

    /** Seconds since the earliest sample currently above [threshold]. */
    fun durationAboveThreshold(threshold: Double, nowMs: Long = System.currentTimeMillis()): Double {
        val above = samples.filter { it.confidence >= threshold }
        if (above.isEmpty()) return 0.0
        val earliest = above.minOf { it.timestampMs }
        return (nowMs - earliest) / 1000.0
    }

    /** True if a single sample spiked far above neighbors (ignored as noise). */
    fun isSingleSpike(threshold: Double): Boolean {
        if (samples.size < 3) return false
        val values = samples.map { it.confidence }
        val max = values.maxOrNull() ?: return false
        if (max < threshold) return false
        val others = values.filter { it != max }
        if (others.isEmpty()) return false
        val avgOthers = others.average()
        return max - avgOthers > 25.0
    }
}
