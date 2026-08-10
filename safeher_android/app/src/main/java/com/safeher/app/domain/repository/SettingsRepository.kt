package com.safeher.app.domain.repository

import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.model.PermissionStatuses
import com.safeher.app.domain.model.SecurityInfo
import com.safeher.app.domain.model.UserProfile
import kotlinx.coroutines.flow.Flow

interface SettingsRepository {

    fun observeNotificationsEnabled(): Flow<Boolean>
    fun observeSosNotificationsEnabled(): Flow<Boolean>
    fun observeHelperNotificationsEnabled(): Flow<Boolean>
    fun observeAiNotificationsEnabled(): Flow<Boolean>
    fun observeAiAudioDetectionEnabled(): Flow<Boolean>
    fun observeAiMovementDetectionEnabled(): Flow<Boolean>
    fun observeAiSensitivity(): Flow<AiSensitivity>
    fun observeAiHelpImproveEnabled(): Flow<Boolean>
    fun observeAiMonitoringEnabled(): Flow<Boolean>
    fun observeThemeMode(): Flow<AppThemeMode>
    fun observeLanguage(): Flow<String>

    suspend fun setNotificationsEnabled(enabled: Boolean)
    suspend fun setSosNotificationsEnabled(enabled: Boolean)
    suspend fun setHelperNotificationsEnabled(enabled: Boolean)
    suspend fun setAiNotificationsEnabled(enabled: Boolean)
    suspend fun setAiAudioDetectionEnabled(enabled: Boolean)
    suspend fun setAiMovementDetectionEnabled(enabled: Boolean)
    suspend fun setAiSensitivity(sensitivity: AiSensitivity)
    suspend fun setAiHelpImproveEnabled(enabled: Boolean)
    suspend fun setAiMonitoringEnabled(enabled: Boolean)
    suspend fun setThemeMode(mode: AppThemeMode)
    suspend fun setLanguage(languageCode: String)

    suspend fun getProfile(): Result<UserProfile>
    suspend fun getSecurityInfo(): SecurityInfo
    fun getPermissionStatuses(): PermissionStatuses
    fun isBatteryOptimizationDisabled(): Boolean
    fun openAppSettings()
    fun openBatteryOptimizationSettings()
    suspend fun logout()
}
