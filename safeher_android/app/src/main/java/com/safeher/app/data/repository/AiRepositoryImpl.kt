package com.safeher.app.data.repository

import com.safeher.app.core.network.AiApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiFeedbackRequestDto
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
import org.json.JSONObject
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
        phraseScore: Float,
        volumeScore: Float,
        detectedPhrase: String?,
        phraseLanguage: String?,
        fallDetected: Boolean,
    ): Result<AiConfidenceResult> = RepositoryApiCall.executeOnline(moshi, networkMonitor) {
        api.getConfidence(
            ConfidenceRequestDto(
                audio_score = audioScore,
                movement_score = movementScore,
                phrase_score = phraseScore,
                volume_score = volumeScore,
                detected_phrase = detectedPhrase,
                phrase_language = phraseLanguage,
                heart_rate_spike = heartRateSpike,
                is_night = isNight,
                is_isolated = isIsolated,
                fall_detected = fallDetected,
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

    override suspend fun submitFeedback(
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
    ): Result<Unit> = try {
        if (!networkMonitor.isOnline.first()) {
            Result.failure(Exception("Offline — feedback skipped"))
        } else {
            api.submitFeedback(
                AiFeedbackRequestDto(
                    event_id = eventId,
                    session_id = sessionId,
                    model_version = modelVersion,
                    signal_type = signalType,
                    prediction_state = predictionState,
                    confidence = confidence,
                    user_feedback = userFeedback,
                    outcome = outcome,
                    consent_granted = consentGranted,
                    consent_version = consentVersion,
                    features = parseNumericFeatures(featuresJson),
                ),
            )
            Timber.i("AI feedback recorded category-event=%s", eventId)
            Result.success(Unit)
        }
    } catch (e: Exception) {
        Timber.w(e, "AI feedback upload failed")
        Result.failure(e)
    }

    private fun parseNumericFeatures(json: String): Map<String, Double>? {
        if (json.isBlank()) return null
        return try {
            val obj = JSONObject(json)
            val out = mutableMapOf<String, Double>()
            val keys = obj.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val value = obj.optDouble(key, Double.NaN)
                if (!value.isNaN()) out[key] = value
            }
            out.ifEmpty { null }
        } catch (_: Exception) {
            null
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
