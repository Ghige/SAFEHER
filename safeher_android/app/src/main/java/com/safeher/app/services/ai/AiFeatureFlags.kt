package com.safeher.app.services.ai

import com.safeher.app.BuildConfig

/**
 * RC1 / Stage 0 feature gates.
 * Movement AI postponed until model + scaler are exported.
 * Automatic AI SOS must stay disabled until production acceptance gates pass.
 * Manual SOS is unaffected.
 */
object AiFeatureFlags {
    /**
     * Movement TFLite not available — movement_v2 is sklearn RandomForest (not convertible
     * to TFLite without retraining). Keep false; do not invent scores.
     */
    const val MOVEMENT_AI_ENABLED = false

    /**
     * Duty-cycled one-shot ASR while AudioRecord is primary (see SpeechAudioCoexistencePolicy).
     * Does not invent phrase scores; only feeds real SpeechRecognizer transcripts.
     */
    const val SPEECH_ASR_INTERLEAVE_ENABLED = true

    /** Hard kill-switch mirrored from BuildConfig (always false until product sign-off). */
    val AI_AUTO_SOS_ENABLED: Boolean
        get() = BuildConfig.AI_AUTO_SOS_ENABLED
}
