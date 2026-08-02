package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class CreateContactRequestDto(
    val name: String,
    val phone_number: String,
    val relationship: String,
    val ring_priority: Int,
)
