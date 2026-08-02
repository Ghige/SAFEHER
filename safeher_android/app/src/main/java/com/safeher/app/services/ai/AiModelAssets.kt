package com.safeher.app.services.ai

/**
 * Documents required on-device AI assets.
 *
 * These files are NOT bundled in the current build. Copy from the backend
 * training pipeline into `app/src/main/assets/` before enabling TFLite inference.
 */
object AiModelAssets {
    const val AUDIO_MODEL = "yamnet_distress_quant.tflite"
    const val MOVEMENT_MODEL = "movement_model.tflite"
    const val MOVEMENT_SCALER = "movement_scaler.pkl"

    val requiredAssets = listOf(
        AUDIO_MODEL,
        MOVEMENT_MODEL,
        MOVEMENT_SCALER,
    )

    /**
     * No labels.txt is required — the audio model outputs a single distress sigmoid (0–100).
     */
}
