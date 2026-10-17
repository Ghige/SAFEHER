package com.safeher.app.services.ai

import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Movement model unavailable on-device — does not invent scores.
 *
 * Backend artifact `movement_v2/movement_model.joblib` is scikit-learn, not TFLite.
 * [AiModelAssets.MOVEMENT_MODEL] is not present in assets.
 */
@Singleton
class MissingMovementInferenceEngine @Inject constructor() : MovementInferenceEngine {

    override val isAvailable: Boolean = false

    val unavailableReason: String = AiModelAssets.MOVEMENT_UNAVAILABLE_REASON

    init {
        Timber.w("AI movement: %s", unavailableReason)
    }

    override suspend fun inferMovement(accelerometerWindow: FloatArray): MovementInferenceEngine.MovementResult? {
        AiDetectionLogger.logMovementSkipped(unavailableReason)
        return null
    }
}
