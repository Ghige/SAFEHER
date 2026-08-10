package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class AudioSosRequestDto(
    val audio_score: Float,
    val movement_score: Float = 0f,
    val latitude: Float? = null,
    val longitude: Float? = null,
    val is_night: Boolean? = null,
    val is_isolated: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class MovementSosRequestDto(
    val movement_score: Float,
    val fall_detected: Boolean = false,
    val audio_score: Float = 0f,
    val latitude: Float? = null,
    val longitude: Float? = null,
    val is_night: Boolean? = null,
    val is_isolated: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class ConfidenceRequestDto(
    val audio_score: Float = 0f,
    val movement_score: Float = 0f,
    val heart_rate_spike: Boolean = false,
    val is_night: Boolean? = null,
    val is_isolated: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class AiConfidenceResponseDto(
    val total_score: Double,
    val action: String,
    val activate_gps_stream: Boolean,
    val audio_score: Double,
    val movement_score: Double,
    val heart_rate_spike: Boolean,
    val is_night: Boolean?,
    val is_isolated: Boolean,
)

@JsonClass(generateAdapter = true)
data class AiFusionDto(
    val total_score: Double,
    val action: String,
    val activate_gps_stream: Boolean,
    val audio_score: Double,
    val movement_score: Double,
    val heart_rate_spike: Boolean,
    val is_night: Boolean?,
    val is_isolated: Boolean,
)

@JsonClass(generateAdapter = true)
data class AiSosResponseDto(
    val fusion: AiFusionDto?,
    val alert: String?,
    val trigger_error: String? = null,
    val reason: String? = null,
)

typealias AiResponseDto = AiConfidenceResponseDto

@JsonClass(generateAdapter = true)
data class AiModelVersionDto(
    val model_type: String,
    val version: String,
    val status: String,
    val artifact_path: String? = null,
)

@JsonClass(generateAdapter = true)
data class AiDatasetQueueResponseDto(
    val sample_id: String,
    val status: String,
)
