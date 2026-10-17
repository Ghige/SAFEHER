package com.safeher.app.services.ai

import java.util.ArrayDeque

/**
 * Short temporal buffer of 1-second distress scores.
 *
 * Horizon is [AiDetectionConfig.evidenceHorizonSeconds] (about 5–7 s by default).
 * Popup / cooldown must not clear this buffer.
 */
class ScoreHistory(
    private val evidenceHorizonSeconds: Double,
    private val maxSamples: Int,
) {
    private val samples = ArrayDeque<ScoreSample>()

    val size: Int get() = samples.size

    fun add(sample: ScoreSample, nowMs: Long = sample.timestampMs) {
        samples.addLast(sample)
        prune(nowMs)
    }

    fun prune(nowMs: Long) {
        val horizonMs = (evidenceHorizonSeconds * 1000.0).toLong().coerceAtLeast(0L)
        val cutoff = nowMs - horizonMs
        while (samples.isNotEmpty() && samples.first().timestampMs < cutoff) {
            samples.removeFirst()
        }
        while (samples.size > maxSamples) {
            samples.removeFirst()
        }
    }

    fun snapshot(): List<ScoreSample> = samples.toList()

    fun latest(): ScoreSample? = samples.lastOrNull()

    fun clear() {
        samples.clear()
    }
}
