package com.safeher.app.feature.sos

import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.feature.sos.util.SosPreflightResult

data class SOSUiState(
    val isLoading: Boolean = false,
    val activeAlert: SafetyAlert? = null,
    val countdownSeconds: Int? = null,
    val isTriggering: Boolean = false,
    val error: String? = null,
    val isOffline: Boolean = false,
    val showCancelDialog: Boolean = false,
    val whatsappWarning: String? = null,
    val heartbeatWarning: Boolean = false,
    val preflight: SosPreflightResult? = null,
    val showLocationWarning: Boolean = false,
    val hasPendingSos: Boolean = false,
    val queuedMessage: String? = null,
)
