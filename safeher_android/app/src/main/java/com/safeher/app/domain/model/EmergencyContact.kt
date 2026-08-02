package com.safeher.app.domain.model

data class EmergencyContact(
    val id: String,
    val name: String,
    val phoneNumber: String,
    val relationship: String?,
    val ringPriority: Int,
    val isActive: Boolean,
)
