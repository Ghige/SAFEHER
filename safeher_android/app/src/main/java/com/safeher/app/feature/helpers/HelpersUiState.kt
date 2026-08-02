package com.safeher.app.feature.helpers

import com.safeher.app.domain.model.NearbyHelper

data class HelpersUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val helpers: List<NearbyHelper> = emptyList(),
    val blockedHelpers: List<NearbyHelper> = emptyList(),
    val activeAlertId: String? = null,
    val error: String? = null,
    val isOffline: Boolean = false,
    val helperToRespond: NearbyHelper? = null,
    val helperToBlock: NearbyHelper? = null,
    val isResponding: Boolean = false,
    val isBlocking: Boolean = false,
    val snackbarMessage: String? = null,
)
