package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ContactDto(
    val id: String,
    val name: String,
    val phone_number: String,
    val relationship: String? = null,
    val ring_priority: Int = 1,
    val is_active: Boolean = true,
)
