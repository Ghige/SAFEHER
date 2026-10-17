package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ScoreHistoryTest {

    @Test
    fun retainsScoresInsideEvidenceHorizon() {
        val history = ScoreHistory(evidenceHorizonSeconds = 6.0, maxSamples = 8)
        history.add(ScoreSample(1, 0L, 10.0))
        history.add(ScoreSample(2, 1_000L, 20.0))
        history.add(ScoreSample(3, 5_000L, 30.0))
        history.prune(nowMs = 7_000L)
        val scores = history.snapshot().map { it.score }
        assertEquals(listOf(20.0, 30.0), scores)
        assertEquals(3L, history.latest()!!.sequence)
    }

    @Test
    fun doesNotClearBecauseAPopupWasShown() {
        val history = ScoreHistory(evidenceHorizonSeconds = 6.0, maxSamples = 8)
        history.add(ScoreSample(1, 1_000L, 80.0), nowMs = 1_000L)
        history.add(ScoreSample(2, 2_000L, 81.0), nowMs = 2_000L)
        // Popup show/dismiss must not wipe history — caller simply keeps adding.
        history.add(ScoreSample(3, 3_000L, 82.0), nowMs = 3_000L)
        assertEquals(3, history.size)
        assertEquals(82.0, history.latest()!!.score, 0.01)
    }

    @Test
    fun respectsMaxSamples() {
        val history = ScoreHistory(evidenceHorizonSeconds = 60.0, maxSamples = 3)
        history.add(ScoreSample(1, 0L, 1.0))
        history.add(ScoreSample(2, 1_000L, 2.0))
        history.add(ScoreSample(3, 2_000L, 3.0))
        history.add(ScoreSample(4, 3_000L, 4.0))
        assertEquals(3, history.size)
        assertEquals(listOf(2.0, 3.0, 4.0), history.snapshot().map { it.score })
    }

    @Test
    fun clearEmptiesHistory() {
        val history = ScoreHistory(evidenceHorizonSeconds = 6.0, maxSamples = 8)
        history.add(ScoreSample(1, 0L, 50.0))
        history.clear()
        assertTrue(history.snapshot().isEmpty())
        assertEquals(null, history.latest())
    }
}
