package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiFeedbackRequestDto
import com.safeher.app.data.remote.dto.AiFeedbackResponseDto
import com.safeher.app.data.remote.dto.AiModelVersionDto
import com.safeher.app.data.remote.dto.AiSosResponseDto
import com.safeher.app.data.remote.dto.AudioSosRequestDto
import com.safeher.app.data.remote.dto.ConfidenceRequestDto
import com.safeher.app.data.remote.dto.MovementSosRequestDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
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

    @POST("api/v1/ai/feedback")
    suspend fun submitFeedback(@Body body: AiFeedbackRequestDto): AiFeedbackResponseDto
}
