package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiDatasetQueueResponseDto
import com.safeher.app.data.remote.dto.AiModelVersionDto
import com.safeher.app.data.remote.dto.AiSosResponseDto
import com.safeher.app.data.remote.dto.AudioSosRequestDto
import com.safeher.app.data.remote.dto.ConfidenceRequestDto
import com.safeher.app.data.remote.dto.MovementSosRequestDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Query

interface AiApi {

    @POST("api/v1/ai/confidence")
    suspend fun getConfidence(@Body request: ConfidenceRequestDto): AiConfidenceResponseDto

    @POST("api/v1/ai/audio-sos")
    suspend fun triggerAudioSos(@Body request: AudioSosRequestDto): AiSosResponseDto

    @POST("api/v1/ai/movement-sos")
    suspend fun triggerMovementSos(@Body request: MovementSosRequestDto): AiSosResponseDto

    @GET("api/v1/ai/models/latest")
    suspend fun getLatestModelVersion(@Query("model_type") modelType: String = "audio"): AiModelVersionDto

    @Multipart
    @POST("api/v1/ai/datasets/queue")
    suspend fun queueDatasetSample(
        @Part audio: MultipartBody.Part,
        @Part("model_version") modelVersion: RequestBody,
        @Part("ai_confidence") aiConfidence: RequestBody,
        @Part("user_confirmation") userConfirmation: RequestBody,
        @Part("label") label: RequestBody,
        @Part("duration_seconds") durationSeconds: RequestBody,
        @Part("features_json") featuresJson: RequestBody,
    ): AiDatasetQueueResponseDto
}
