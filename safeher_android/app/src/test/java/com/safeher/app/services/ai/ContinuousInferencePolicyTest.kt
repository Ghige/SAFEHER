package com.safeher.app.services.ai

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContinuousInferencePolicyTest {

    @Test
    fun scoresInForegroundWhileMonitoring() {
        assertTrue(
            ContinuousInferencePolicy.shouldScore(
                monitoringActive = true,
                appInForeground = true,
                microphoneFgsRunning = false,
            ),
        )
    }

    @Test
    fun scoresInBackgroundOnlyWhenMicrophoneFgsAlreadyRunning() {
        assertTrue(
            ContinuousInferencePolicy.shouldScore(
                monitoringActive = true,
                appInForeground = false,
                microphoneFgsRunning = true,
            ),
        )
        assertFalse(
            ContinuousInferencePolicy.shouldScore(
                monitoringActive = true,
                appInForeground = false,
                microphoneFgsRunning = false,
            ),
        )
    }

    @Test
    fun neverScoresWhenMonitoringOff() {
        assertFalse(
            ContinuousInferencePolicy.shouldScore(
                monitoringActive = false,
                appInForeground = true,
                microphoneFgsRunning = true,
            ),
        )
    }

    @Test
    fun popupUiNeverStopsInference() {
        assertFalse(
            ContinuousInferencePolicy.popupUiStopsInference(
                popupVisible = true,
                cooldownActive = true,
                frequencyLimited = true,
            ),
        )
    }
}
