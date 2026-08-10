package com.safeher.app.services.ai

/**
 * Required on-device AI assets.
 *
 * Audio: copy `yamnet_distress_quant.tflite` from safeher_ai/models/final/ into assets/.
 * Movement: postponed for RC1 — model and scaler not yet exported.
 */
object AiModelAssets {
    const val AUDIO_MODEL = "yamnet_distress_quant.tflite"
    const val MOVEMENT_MODEL = "movement_model.tflite"
    const val MOVEMENT_SCALER = "movement_scaler.pkl"

    val requiredAssetsForRc1 = listOf(AUDIO_MODEL)

    /**
     * No labels.txt is required — the audio model outputs a single distress sigmoid (0–100).
     */
}
