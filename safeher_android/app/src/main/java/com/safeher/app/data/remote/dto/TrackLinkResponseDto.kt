package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class TrackLinkResponseDto(
    val track_url: String,
    val expires_in_hours: Int,
)
