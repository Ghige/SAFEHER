package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Test

class AiScoreThresholdsTest {

    @Test
    fun tiers_matchUnifiedContractV1() {
        assertEquals(20, AiScoreThresholds.TIER_SILENT_VIBRATION)
        assertEquals(40, AiScoreThresholds.TIER_CONFIRM_30S)
        assertEquals(65, AiScoreThresholds.TIER_IMMEDIATE_SOS)
        assertEquals(55, AiScoreThresholds.DISTRESS_MEDIUM)
        assertEquals(70, AiScoreThresholds.DISTRESS_HIGH)
        assertEquals(55, AiScoreThresholds.SENSOR_NOISE_FLOOR)
        assertEquals(30, AiScoreThresholds.CONFIRM_COUNTDOWN_SECONDS)
        assertEquals(DecisionContract.CONFIRM_COUNTDOWN_SECONDS, AiScoreThresholds.CONFIRM_COUNTDOWN_SECONDS)
    }
}
