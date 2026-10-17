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

    /** Status/log alias for the V2 classifier asset. Does not change the inference pipeline. */
    const val AUDIO_MODEL = AUDIO_CLASSIFIER_MODEL

    const val MOVEMENT_MODEL = "movement_model.tflite"

    const val MOVEMENT_SCALER = "movement_scaler.pkl"

    const val MOVEMENT_UNAVAILABLE_REASON =
        "movement_v2 is sklearn joblib (RandomForest); no movement_model.tflite in assets. " +
            "On-device movement inference disabled — IMU may still be collected for levels only."

    val requiredAssetsForRc1 = listOf(
        YAMNET_EMBEDDING_MODEL,
        AUDIO_CLASSIFIER_MODEL,
    )
}