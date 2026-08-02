package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class OtpVerifyRequestDto(
    val phone_number: String,
    val otp: String,
)
