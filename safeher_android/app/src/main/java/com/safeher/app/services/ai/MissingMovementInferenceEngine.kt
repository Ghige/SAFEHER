package com.safeher.app.services.ai

import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Placeholder until [AiModelAssets.MOVEMENT_MODEL] and scaler are added to assets
 * and TensorFlow Lite dependencies are configured.
 */
@Singleton
class MissingMovementInferenceEngine @Inject constructor() : MovementInferenceEngine {

    override val isAvailable: Boolean = false

    init {
        Timber.w(
            "AI movement model missing — add ${AiModelAssets.MOVEMENT_MODEL} and " +
                "${AiModelAssets.MOVEMENT_SCALER} to assets/ and implement TfliteMovementInferenceEngine",
        )
    }

    override suspend fun inferMovement(accelerometerWindow: FloatArray): MovementInferenceEngine.MovementResult? = null
}
