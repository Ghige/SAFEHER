package com.safeher.app.domain.model

data class UserProfile(
    val id: String,
    val phoneNumber: String,
    val name: String,
    val city: String?,
    val isVerified: Boolean,
)
