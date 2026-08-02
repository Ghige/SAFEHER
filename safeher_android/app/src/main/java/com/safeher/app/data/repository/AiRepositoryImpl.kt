package com.safeher.app.data.repository

import com.safeher.app.core.network.AiApi
import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiFusionDto
import com.safeher.app.data.remote.dto.AiSosResponseDto
import com.safeher.app.data.remote.dto.AudioSosRequestDto
import com.safeher.app.data.remote.dto.ConfidenceRequestDto
import com.safeher.app.data.remote.dto.MovementSosRequestDto
import com.safeher.app.domain.model.AiAction
import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.domain.model.AiSosResult
import com.safeher.app.domain.repository.AiRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AiRepositoryImpl @Inject constructor(
    private val api: AiApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : AiRepository {

    override suspend fun getConfidence(
        audioScore: Float,
        movementScore: Float,
        heartRateSpike: Boolean,
        isNight: Boolean?,
        isIsolated: Boolean,
    ): Result<AiConfidenceResult> = apiCall {
        api.getConfidence(
            ConfidenceRequestDto(
                audio_score = audioScore,
                movement_score = movementScore,
                heart_rate_spike = heartRateSpike,
                is_night = isNight,
                is_isolated = isIsolated,
            ),
        ).toDomain()
    }

    override suspend fun triggerAudioSos(
        audioScore: Float,
        movementScore: Float,
        latitude: Float?,
        longitude: Float?,
        isNight: Boolean?,
        isIsolated: Boolean,
    ): Result<AiSosResult> = apiCall {
        api.triggerAudioSos(
            AudioSosRequestDto(
                audio_score = audioScore,
                movement_score = movementScore,
                latitude = latitude,
                longitude = longitude,
                is_night = isNight,
                is_isolated = isIsolated,
            ),
        ).toDomain()
    }

    override suspend fun triggerMovementSos(
        movementScore: Float,
        fallDetected: Boolean,
        audioScore: Float,
        latitude: Float?,
        longitude: Float?,
        isNight: Boolean?,
        isIsolated: Boolean,
    ): Result<AiSosResult> = apiCall {
        api.triggerMovementSos(
            MovementSosRequestDto(
                movement_score = movementScore,
                fall_detected = fallDetected,
                audio_score = audioScore,
                latitude = latitude,
                longitude = longitude,
                is_night = isNight,
                is_isolated = isIsolated,
            ),
        ).toDomain()
    }

    private suspend inline fun <T> apiCall(block: () -> T): Result<T> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                Result.failure(Exception("You are offline. Connect to the internet and try again."))
            } else {
                Result.success(block())
            }
        } catch (e: HttpException) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }

    private fun AiConfidenceResponseDto.toDomain() = AiConfidenceResult(
        totalScore = total_score,
        action = AiAction.fromBackend(action),
        activateGpsStream = activate_gps_stream,
        audioScore = audio_score,
        movementScore = movement_score,
        heartRateSpike = heart_rate_spike,
        isNight = is_night,
        isIsolated = is_isolated,
    )

    private fun AiFusionDto.toDomain() = AiConfidenceResult(
        totalScore = total_score,
        action = AiAction.fromBackend(action),
        activateGpsStream = activate_gps_stream,
        audioScore = audio_score,
        movementScore = movement_score,
        heartRateSpike = heart_rate_spike,
        isNight = is_night,
        isIsolated = is_isolated,
    )

    private fun AiSosResponseDto.toDomain() = AiSosResult(
        fusion = fusion?.toDomain(),
        alertId = alert,
        triggerError = trigger_error,
        reason = reason,
    )
}
