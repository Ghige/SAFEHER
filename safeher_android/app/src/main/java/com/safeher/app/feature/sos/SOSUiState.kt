package com.safeher.app.feature.sos

import com.safeher.app.domain.model.SafetyAlert

data class SOSUiState(
    val isLoading: Boolean = false,
    val activeAlert: SafetyAlert? = null,
    val countdownSeconds: Int? = null,
    val isTriggering: Boolean = false,
    val error: String? = null,
    val isOffline: Boolean = false,
    val showCancelDialog: Boolean = false,
)
