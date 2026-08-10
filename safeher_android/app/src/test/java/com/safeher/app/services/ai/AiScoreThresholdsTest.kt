package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Test

class AiScoreThresholdsTest {

    @Test
    fun tiers_matchBackendConfidenceScorer() {
        assertEquals(60, AiScoreThresholds.SENSOR_NOISE_FLOOR)
        assertEquals(40, AiScoreThresholds.TIER_SILENT_VIBRATION)
        assertEquals(60, AiScoreThresholds.TIER_CONFIRM_30S)
        assertEquals(80, AiScoreThresholds.TIER_IMMEDIATE_SOS)
    }
}
