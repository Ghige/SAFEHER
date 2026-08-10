package com.safeher.app.data.repository

import com.safeher.app.core.network.AiApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.RepositoryApiCall
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
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import timber.log.Timber
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
    ): Result<AiConfidenceResult> = RepositoryApiCall.executeOnline(moshi, networkMonitor) {
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
    ): Result<AiSosResult> = RepositoryApiCall.executeOnline(moshi, networkMonitor) {
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
    ): Result<AiSosResult> = RepositoryApiCall.executeOnline(moshi, networkMonitor) {
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

    override suspend fun getLatestModelVersion(modelType: String): Result<String> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.getLatestModelVersion(modelType).version
        }

    override suspend fun queueDatasetSample(
        audioWav: ByteArray,
        modelVersion: String,
        aiConfidence: Float,
        userConfirmation: Boolean,
        label: String,
        durationSeconds: Float,
        featuresJson: String,
    ): Result<Unit> = try {
        if (!networkMonitor.isOnline.first()) {
            Result.failure(Exception("Offline — dataset upload skipped"))
        } else {
            val textType = "text/plain".toMediaType()
            val audioPart = MultipartBody.Part.createFormData(
                "audio",
                "clip.wav",
                audioWav.toRequestBody("audio/wav".toMediaType()),
            )
            api.queueDatasetSample(
                audio = audioPart,
                modelVersion = modelVersion.toRequestBody(textType),
                aiConfidence = aiConfidence.toString().toRequestBody(textType),
                userConfirmation = userConfirmation.toString().toRequestBody(textType),
                label = label.toRequestBody(textType),
                durationSeconds = durationSeconds.toString().toRequestBody(textType),
                featuresJson = featuresJson.toRequestBody(textType),
            )
            Timber.i("AI dataset sample queued label=%s model=%s", label, modelVersion)
            Result.success(Unit)
        }
    } catch (e: Exception) {
        Timber.w(e, "AI dataset upload failed")
        Result.failure(e)
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
