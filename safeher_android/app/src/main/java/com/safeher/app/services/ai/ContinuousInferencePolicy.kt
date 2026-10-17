package com.safeher.app.services.ai

/**
 * Scoring continues while monitoring is active. Popup cooldown, a visible popup,
 * and popup frequency limits never stop inference.
 *
 * Background scoring is allowed only while the existing microphone foreground
 * service is already running (it must have been started from the foreground).
 * This policy does not start a new FGS from the background.
 */
object ContinuousInferencePolicy {

    fun shouldScore(
        monitoringActive: Boolean,
        appInForeground: Boolean,
        microphoneFgsRunning: Boolean,
    ): Boolean {
        if (!monitoringActive) return false
        if (appInForeground) return true
        return microphoneFgsRunning
    }

    /** Contract: UI popup state is not an inference gate. */
    @Suppress("UNUSED_PARAMETER")
    fun popupUiStopsInference(
        popupVisible: Boolean,
        cooldownActive: Boolean,
        frequencyLimited: Boolean,
    ): Boolean = false
}
