package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiSosResponseDto
import com.safeher.app.data.remote.dto.AudioSosRequestDto
import com.safeher.app.data.remote.dto.ConfidenceRequestDto
import com.safeher.app.data.remote.dto.MovementSosRequestDto
import retrofit2.http.Body
import retrofit2.http.POST

interface AiApi {

    @POST("api/v1/ai/confidence")
    suspend fun getConfidence(@Body request: ConfidenceRequestDto): AiConfidenceResponseDto

    @POST("api/v1/ai/audio-sos")
    suspend fun triggerAudioSos(@Body request: AudioSosRequestDto): AiSosResponseDto

    @POST("api/v1/ai/movement-sos")
    suspend fun triggerMovementSos(@Body request: MovementSosRequestDto): AiSosResponseDto
}
