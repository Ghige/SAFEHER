package com.safeher.app.feature.sos

enum class AlertHistoryFilter {
    ALL,
    SOS,
    AI,
    LOCATION,
}

data class AlertHistoryUiState(
    val isLoading: Boolean = true,
    val history: List<com.safeher.app.domain.model.SafetyAlert> = emptyList(),
    val filteredHistory: List<com.safeher.app.domain.model.SafetyAlert> = emptyList(),
    val selectedFilter: AlertHistoryFilter = AlertHistoryFilter.ALL,
    val error: String? = null,
    val isOffline: Boolean = false,
)
