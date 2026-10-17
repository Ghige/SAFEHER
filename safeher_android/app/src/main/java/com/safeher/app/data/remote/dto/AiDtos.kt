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
    val phrase_score: Float = 0f,
    val volume_score: Float = 0f,
    val detected_phrase: String? = null,
    val phrase_language: String? = null,
    val heart_rate_spike: Boolean = false,
    val is_night: Boolean? = null,
    val is_isolated: Boolean = false,
    val fall_detected: Boolean = false,
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
    val risk_level: String? = null,
    val risk_score: Double? = null,
    val reason_codes: List<String>? = null,
    val phrase_score: Double? = null,
    val detected_phrase: String? = null,
    val phrase_language: String? = null,
    val should_confirm: Boolean? = null,
    val should_trigger_sos: Boolean? = null,
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

@JsonClass(generateAdapter = true)
data class AiFeedbackRequestDto(
    val event_id: String,
    val session_id: String,
    val model_version: String,
    val signal_type: String,
    val prediction_state: String,
    val confidence: Double,
    val user_feedback: String,
    val outcome: String,
    val consent_granted: Boolean,
    val consent_version: String,
    val features: Map<String, Double>? = null,
)

@JsonClass(generateAdapter = true)
data class AiFeedbackResponseDto(
    val event_id: String,
    val candidate_category: String,
    val review_status: String,
    val gold_eligible: Boolean = false,
    val fp_fn_status: String? = null,
)
