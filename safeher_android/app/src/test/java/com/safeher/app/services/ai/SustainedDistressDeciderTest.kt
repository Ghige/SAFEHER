package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SustainedDistressDeciderTest {

    private val config = AiDetectionConfig()
    private val decider = SustainedDistressDecider(config)

    @Test
    fun defaultThresholdIsConfigurable_notHardCodedFinal() {
        val custom = AiDetectionConfig(confidenceThreshold = 60.0, consecutiveHotRequired = 3)
        val customDecider = SustainedDistressDecider(custom)
        val history = listOf(
            ScoreSample(1, 0L, 61.0),
            ScoreSample(2, 1_000L, 62.0),
            ScoreSample(3, 2_000L, 63.0),
        )
        val decision = customDecider.evaluate(history, nowMs = 2_000L)
        assertEquals(60.0, decision.threshold, 0.01)
        assertTrue(decision.isSustained)
        assertEquals(75.0, config.confidenceThreshold, 0.01)
    }

    @Test
    fun singleHighScore_isWatch_notSustained() {
        val history = listOf(ScoreSample(1, 1_000L, 99.0))
        val decision = decider.evaluate(history, nowMs = 1_000L)
        assertEquals(TemporalState.WATCH, decision.state)
        assertFalse(decision.isSustained)
        assertEquals(1, decision.consecutiveHot)
    }

    @Test
    fun threeConsecutiveHot_isSustained() {
        val history = listOf(
            ScoreSample(1, 0L, 80.0),
            ScoreSample(2, 1_000L, 81.0),
            ScoreSample(3, 2_000L, 82.0),
        )
        val decision = decider.evaluate(history, nowMs = 2_000L)
        assertTrue(decision.consecutiveSatisfied)
        assertTrue(decision.isSustained)
        assertEquals(TemporalState.SUSTAINED, decision.state)
        assertTrue(decision.episodeId != null)
    }

    @Test
    fun nOfM_canSustainWithoutConsecutiveRun() {
        val history = listOf(
            ScoreSample(1, 0L, 80.0),
            ScoreSample(2, 1_000L, 10.0),
            ScoreSample(3, 2_000L, 81.0),
            ScoreSample(4, 3_000L, 82.0),
            ScoreSample(5, 4_000L, 11.0),
            ScoreSample(6, 5_000L, 83.0),
        )
        val decision = decider.evaluate(history, nowMs = 5_000L)
        assertEquals(1, decision.consecutiveHot)
        assertTrue(decision.nOfMSatisfied)
        assertTrue(decision.isSustained)
    }

    @Test
    fun consecutiveOnlyConfig_ignoresScatteredHot() {
        val consecutiveOnly = SustainedDistressDecider(
            AiDetectionConfig(useConsecutiveHotLogic = true, allowNOfMLogic = false),
        )
        val history = listOf(
            ScoreSample(1, 0L, 80.0),
            ScoreSample(2, 1_000L, 10.0),
            ScoreSample(3, 2_000L, 81.0),
            ScoreSample(4, 3_000L, 82.0),
            ScoreSample(5, 4_000L, 11.0),
            ScoreSample(6, 5_000L, 83.0),
        )
        val decision = consecutiveOnly.evaluate(history, nowMs = 5_000L)
        assertFalse(decision.consecutiveSatisfied)
        assertFalse(decision.isSustained)
        assertEquals(TemporalState.WATCH, decision.state)
    }
}
