package com.safeher.app.domain.model

data class SafetyAlert(
    val id: String,
    val triggerType: String,
    val latitude: Double?,
    val longitude: Double?,
    val status: String,
    val startedAt: String,
    val endedAt: String?,
    val evidenceUrl: String?,
    val whatsappSentCount: Int? = null,
    val whatsappFailedCount: Int? = null,
    val whatsappAllDelivered: Boolean? = null,
) {
    val isOngoing: Boolean
        get() = status == "active" || status == "escalated"
}
