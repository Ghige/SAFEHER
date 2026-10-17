package com.safeher.app.services.ai

/**
 * Extension point for on-device movement / fall inference.
 *
 * Implement with TFLite when [AiModelAssets.MOVEMENT_MODEL] and
 * [AiModelAssets.MOVEMENT_SCALER] are bundled in assets.
 * Returns null when models are unavailable — callers must NOT invent scores.
 */
interface MovementInferenceEngine {
    val isAvailable: Boolean

    data class MovementResult(
        /** Anomaly score 0–100 (same scale as audio TFLite). */
        val movementScore: Double,
        val fallDetected: Boolean,
    )

    /** @return movement inference, or null if inference cannot run */
    suspend fun inferMovement(accelerometerWindow: FloatArray): MovementResult?
}
