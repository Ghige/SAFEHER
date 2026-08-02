package com.safeher.app.services.ai

import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Placeholder until [AiModelAssets.AUDIO_MODEL] is added to assets and
 * TensorFlow Lite dependencies are configured.
 */
@Singleton
class MissingAudioInferenceEngine @Inject constructor() : AudioInferenceEngine {

    override val isAvailable: Boolean = false

    init {
        Timber.w(
            "AI audio model missing — add ${AiModelAssets.AUDIO_MODEL} to assets/ " +
                "and implement TfliteAudioInferenceEngine",
        )
    }

    override suspend fun inferDistressScore(audioSamples: ShortArray, sampleRate: Int): Double? = null
}
