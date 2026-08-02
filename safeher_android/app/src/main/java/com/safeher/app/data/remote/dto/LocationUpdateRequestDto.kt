package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LocationUpdateRequestDto(
    val alert_id: String,
    val latitude: Double,
    val longitude: Double,
)
