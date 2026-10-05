package com.safeher.app.services.ai

/**
 * Required on-device AI assets.
 *
 * Audio V2 pipeline:
 *
 * raw PCM audio
 *      ↓
 * yamnet_embedding.tflite
 *      ↓
 * 1024-D YAMNet embedding
 *      ↓
 * safeher_classifier_v2.tflite
 *      ↓
 * distress probability
 *
 * Movement: postponed for RC1.
 */
object AiModelAssets {

    const val YAMNET_EMBEDDING_MODEL = "yamnet_embedding.tflite"

    const val AUDIO_CLASSIFIER_MODEL = "safeher_classifier_v2.tflite"

    const val MOVEMENT_MODEL = "movement_model.tflite"

    const val MOVEMENT_SCALER = "movement_scaler.pkl"

    val requiredAssetsForRc1 = listOf(
        YAMNET_EMBEDDING_MODEL,
        AUDIO_CLASSIFIER_MODEL,
    )
}