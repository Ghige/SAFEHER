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
}
