package com.safeher.app.domain.model

data class NearbyHelper(
    val id: String,
    val alertId: String,
    val status: String,
    val notifiedAt: String,
    val identityRevealed: Boolean,
    val approvedByUser: Boolean,
    val name: String?,
    val phoneNumber: String?,
) {
    val isBlocked: Boolean
        get() = status == "cancelled"

    val canRespond: Boolean
        get() = status == "notified"

    val displayName: String
        get() = when {
            identityRevealed && !name.isNullOrBlank() -> name
            else -> "Helper ${id.take(8)}"
        }

    val availabilityLabel: String
        get() = when (status) {
            "notified" -> "Available"
            "responding" -> "Responding"
            "arrived" -> "Arrived"
            "cancelled" -> "Blocked"
            else -> status.replaceFirstChar { it.uppercase() }
        }

    val distanceLabel: String
        get() = "Nearby"
}
