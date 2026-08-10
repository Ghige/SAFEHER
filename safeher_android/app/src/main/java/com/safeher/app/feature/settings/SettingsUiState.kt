package com.safeher.app.feature.settings

import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.model.PermissionStatuses
import com.safeher.app.domain.model.SecurityInfo
import com.safeher.app.domain.model.UserProfile

data class SettingsUiState(
    val isLoading: Boolean = true,
    val isOffline: Boolean = false,
    val profile: UserProfile? = null,
    val securityInfo: SecurityInfo? = null,
    val permissionStatuses: PermissionStatuses? = null,
    val isBatteryOptimizationDisabled: Boolean = false,
    val notificationsEnabled: Boolean = true,
    val sosNotificationsEnabled: Boolean = true,
    val helperNotificationsEnabled: Boolean = true,
    val aiNotificationsEnabled: Boolean = true,
    val aiMonitoringEnabled: Boolean = false,
    val aiAudioDetectionEnabled: Boolean = true,
    val aiMovementDetectionEnabled: Boolean = true,
    val aiSensitivity: AiSensitivity = AiSensitivity.MEDIUM,
    val aiHelpImproveEnabled: Boolean = false,
    val themeMode: AppThemeMode = AppThemeMode.SYSTEM,
    val language: String = "en",
    val isLoggingOut: Boolean = false,
    val error: String? = null,
)
