package com.safeher.app.services.ai

/** One 1-second model score with capture identity. Never stores PCM. */
data class ScoreSample(
    val sequence: Long,
    val timestampMs: Long,
    val score: Double,
)
