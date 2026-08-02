package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class UserProfileDto(
    val id: String,
    val phone_number: String,
    val name: String,
    val city: String? = null,
)
