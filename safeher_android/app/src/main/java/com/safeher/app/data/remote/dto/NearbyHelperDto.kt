package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class NearbyHelperDto(
    val id: String,
    val alert_id: String,
    val status: String,
    val notified_at: String,
    val identity_revealed: Boolean,
    val approved_by_user: Boolean,
    val name: String? = null,
    val phone_number: String? = null,
)
