package com.safeher.app.feature.dashboard

import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.model.UserProfile

enum class AiHomeStatus {
    NORMAL,
    LISTENING,
    DETECTING,
    OFF,
}

data class DashboardUiState(
    val isLoading: Boolean = true,
    val profile: UserProfile? = null,
    val error: String? = null,
    val isOffline: Boolean = false,
    val isEmpty: Boolean = false,
    val emergencyContacts: List<EmergencyContact> = emptyList(),
    val isLocationSharingActive: Boolean = false,
    val aiMonitoringEnabled: Boolean = false,
    val aiIsMonitoring: Boolean = false,
    val aiStatus: AiHomeStatus = AiHomeStatus.OFF,
    val aiRollingConfidence: Double? = null,
)
