package com.safeher.app.services.ai

/**
 * Stage-4 on-device model availability — never invent scores for unavailable models.
 */
data class AiModelRuntimeStatus(
    val audioAvailable: Boolean,
    val audioAsset: String = AiModelAssets.AUDIO_MODEL,
    val audioDetail: String,
    val speechMode: SpeechMode,
    val speechDetail: String,
    val movementAvailable: Boolean,
    val movementDetail: String,
    val contractVersion: String = DecisionContract.CONTRACT_VERSION,
    val aiAutoSosEnabled: Boolean = AiFeatureFlags.AI_AUTO_SOS_ENABLED,
) {
    enum class SpeechMode {
        /** Catalog matcher ready; ASR transcript may be null while mic owned by AudioRecord. */
        CATALOG_READY,
        /** ASR feeding transcripts into catalog. */
        ASR_ACTIVE,
        /** sklearn speech_v2.joblib cannot run on Android TFLite stack. */
        SKLEARN_UNSUPPORTED,
    }

    val anyInferenceReady: Boolean get() = audioAvailable
}

/**
 * Per-cycle inference diagnostics for UI / logcat (no raw PCM).
 */
data class AiInferenceSnapshot(
    val timestampMs: Long = System.currentTimeMillis(),
    val audioLatencyMs: Long? = null,
    val pipelineLatencyMs: Long? = null,
    val audioScore0to100: Double? = null,
    val phraseScore0to1: Double? = null,
    val detectedPhrase: String? = null,
    val movementScore0to100: Double? = null,
    val fallDetected: Boolean = false,
    val localState: String? = null,
    val localAction: String? = null,
    val lastError: String? = null,
    val movementModelAvailable: Boolean = false,
    val speechMode: AiModelRuntimeStatus.SpeechMode = AiModelRuntimeStatus.SpeechMode.CATALOG_READY,
    val windowSequence: Long? = null,
    val windowTimestampMs: Long? = null,
    val temporalState: String? = null,
    val popupEligible: Boolean? = null,
    val popupSuppressionReason: String? = null,
)
