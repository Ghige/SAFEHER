package com.safeher.app.domain.repository

import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.domain.model.AiSosResult

interface AiRepository {

    suspend fun getConfidence(
        audioScore: Float,
        movementScore: Float,
        heartRateSpike: Boolean = false,
        isNight: Boolean? = null,
        isIsolated: Boolean = false,
        phraseScore: Float = 0f,
        volumeScore: Float = 0f,
        detectedPhrase: String? = null,
        phraseLanguage: String? = null,
        fallDetected: Boolean = false,
    ): Result<AiConfidenceResult>

    suspend fun triggerAudioSos(
        audioScore: Float,
        movementScore: Float = 0f,
        latitude: Float? = null,
        longitude: Float? = null,
        isNight: Boolean? = null,
        isIsolated: Boolean = false,
    ): Result<AiSosResult>

    suspend fun triggerMovementSos(
        movementScore: Float,
        fallDetected: Boolean = false,
        audioScore: Float = 0f,
        latitude: Float? = null,
        longitude: Float? = null,
        isNight: Boolean? = null,
        isIsolated: Boolean = false,
    ): Result<AiSosResult>

    suspend fun getLatestModelVersion(modelType: String = "audio"): Result<String>

    suspend fun submitFeedback(
        eventId: String,
        sessionId: String,
        modelVersion: String,
        signalType: String,
        predictionState: String,
        confidence: Double,
        userFeedback: String,
        outcome: String,
        consentGranted: Boolean,
        consentVersion: String,
        featuresJson: String,
    ): Result<Unit>
}
