package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LiveLocationResponseDto(
    val alert_id: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val status: String,
    val started_at: String,
    val maps_embed: String? = null,
)
