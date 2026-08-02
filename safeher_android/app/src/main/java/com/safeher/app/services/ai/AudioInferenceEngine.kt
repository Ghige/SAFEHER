package com.safeher.app.services.ai

/**
 * Extension point for on-device audio distress inference.
 *
 * Implement with TFLite when [AiModelAssets.AUDIO_MODEL] is bundled in assets.
 * Returns null when models are unavailable — callers must NOT invent scores.
 */
interface AudioInferenceEngine {
    val isAvailable: Boolean

    /** @return distress score 0–100, or null if inference cannot run */
    suspend fun inferDistressScore(audioSamples: ShortArray, sampleRate: Int): Double?
}
