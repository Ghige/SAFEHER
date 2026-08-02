package com.safeher.app.feature.ai

import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.services.AudioPermissionStatus

data class AiMonitoringUiState(
    val isLoading: Boolean = false,
    val isMonitoring: Boolean = false,
    val monitoringEnabled: Boolean = false,
    val modelsAvailable: Boolean = false,
    val isOffline: Boolean = false,
    val isAppInForeground: Boolean = true,
    val audioLevel: Float = 0f,
    val movementLevel: Float = 0f,
    val confidence: AiConfidenceResult? = null,
    val isLoadingConfidence: Boolean = false,
    val isIsolated: Boolean = false,
    val audioPermissionStatus: AudioPermissionStatus = AudioPermissionStatus.DENIED,
    val error: String? = null,
    val snackbarMessage: String? = null,
)
