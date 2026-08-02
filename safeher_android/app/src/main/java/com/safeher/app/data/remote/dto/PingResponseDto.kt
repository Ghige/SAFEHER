package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class PingResponseDto(
    val status: String,
    val alert_id: String,
)
