package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class AlertResponseDto(
    val id: String,
    val trigger_type: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val status: String,
    val started_at: String,
    val ended_at: String? = null,
    val evidence_url: String? = null,
    val whatsapp_sent_count: Int? = null,
    val whatsapp_failed_count: Int? = null,
    val whatsapp_all_delivered: Boolean? = null,
)
