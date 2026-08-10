package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class DeviceTokenRequestDto(
    val fcm_token: String,
)
