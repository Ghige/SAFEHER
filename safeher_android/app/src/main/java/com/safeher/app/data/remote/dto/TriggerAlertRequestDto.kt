package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class TriggerAlertRequestDto(
    val trigger_type: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
)
