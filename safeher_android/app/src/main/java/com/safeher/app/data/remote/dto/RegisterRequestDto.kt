package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class RegisterRequestDto(
    val phone_number: String,
    val name: String,
    val password: String,
    val city: String? = null,
)
