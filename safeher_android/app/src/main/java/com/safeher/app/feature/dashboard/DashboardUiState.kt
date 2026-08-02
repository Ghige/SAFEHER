package com.safeher.app.feature.dashboard

import com.safeher.app.domain.model.UserProfile

data class DashboardUiState(
    val isLoading: Boolean = true,
    val profile: UserProfile? = null,
    val error: String? = null,
    val isOffline: Boolean = false,
    val isEmpty: Boolean = false,
)
