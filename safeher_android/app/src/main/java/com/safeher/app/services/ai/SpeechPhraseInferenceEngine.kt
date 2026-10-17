package com.safeher.app.services.ai

import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

/**
 * On-device speech path for Stage 4.
 *
 * - Production speech_v2 (sklearn .joblib) cannot run in the Android TFLite runtime.
 * - This engine uses [EmergencyPhraseDetector] + [DecisionContract] phrase gates.
 * - Transcripts come from [SpeechTranscriptStore] (ASR when mic is free, or debug inject).
 */
@Singleton
class SpeechPhraseInferenceEngine @Inject constructor(
    private val transcriptStore: SpeechTranscriptStore,
) {
    val mode: AiModelRuntimeStatus.SpeechMode
        get() = if (transcriptStore.asrActive) {
            AiModelRuntimeStatus.SpeechMode.ASR_ACTIVE
        } else {
            AiModelRuntimeStatus.SpeechMode.CATALOG_READY
        }

    val detail: String
        get() = when (mode) {
            AiModelRuntimeStatus.SpeechMode.ASR_ACTIVE ->
                "ASR → EmergencyPhraseDetector (${SpeechAudioCoexistencePolicy.STRATEGY_SUMMARY})"
            AiModelRuntimeStatus.SpeechMode.CATALOG_READY ->
                "Catalog ready; ${SpeechAudioCoexistencePolicy.STRATEGY_SUMMARY}; " +
                    "speech_v2.joblib unsupported on-device"
            AiModelRuntimeStatus.SpeechMode.SKLEARN_UNSUPPORTED ->
                "speech_v2.joblib requires scikit-learn — not loadable on Android"
        }

    fun inferFromLatestTranscript(): EmergencyPhraseDetector.Result {
        val transcript = transcriptStore.latestTranscript
        val result = EmergencyPhraseDetector.detect(transcript)
        if (result.phraseDetected) {
            Timber.d(
                "Speech phrase hit phrase=%s score=%.2f lang=%s",
                result.phrase,
                result.phraseScore,
                result.language,
            )
        }
        return result
    }
}
