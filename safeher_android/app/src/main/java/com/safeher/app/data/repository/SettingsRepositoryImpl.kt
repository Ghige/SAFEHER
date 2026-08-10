package com.safeher.app.data.repository

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import com.safeher.app.BuildConfig
import com.safeher.app.core.datastore.AiSettingsStore
import com.safeher.app.core.datastore.SecureTokenStore
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.session.AuthSessionManager
import com.safeher.app.core.session.SessionCleanupManager
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.model.PermissionDisplayStatus
import com.safeher.app.domain.model.PermissionStatuses
import com.safeher.app.domain.model.SecurityInfo
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.SettingsRepository
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.services.AudioPermissionManager
import com.safeher.app.services.BatteryOptimizationManager
import com.safeher.app.services.LocationPermissionManager
import com.safeher.app.services.NotificationPermissionManager
import dagger.hilt.android.qualifiers.ApplicationContext
import android.content.Context
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SettingsRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context,
    private val settingsStore: SettingsStore,
    private val aiSettingsStore: AiSettingsStore,
    private val userRepository: UserRepository,
    private val secureTokenStore: SecureTokenStore,
    private val authSessionManager: AuthSessionManager,
    private val sessionCleanupManager: SessionCleanupManager,
    private val userPreferences: UserPreferences,
    private val locationPermissionManager: LocationPermissionManager,
    private val audioPermissionManager: AudioPermissionManager,
    private val notificationPermissionManager: NotificationPermissionManager,
    private val batteryOptimizationManager: BatteryOptimizationManager,
) : SettingsRepository {

    override fun observeNotificationsEnabled(): Flow<Boolean> = settingsStore.notificationsEnabled
    override fun observeSosNotificationsEnabled(): Flow<Boolean> = settingsStore.sosNotificationsEnabled
    override fun observeHelperNotificationsEnabled(): Flow<Boolean> = settingsStore.helperNotificationsEnabled
    override fun observeAiNotificationsEnabled(): Flow<Boolean> = settingsStore.aiNotificationsEnabled
    override fun observeAiAudioDetectionEnabled(): Flow<Boolean> = settingsStore.aiAudioDetectionEnabled
    override fun observeAiMovementDetectionEnabled(): Flow<Boolean> = settingsStore.aiMovementDetectionEnabled
    override fun observeAiSensitivity(): Flow<AiSensitivity> = settingsStore.aiSensitivity
    override fun observeAiHelpImproveEnabled(): Flow<Boolean> = settingsStore.aiHelpImproveEnabled
    override fun observeAiMonitoringEnabled(): Flow<Boolean> = aiSettingsStore.monitoringEnabled
    override fun observeThemeMode(): Flow<AppThemeMode> = settingsStore.themeMode
    override fun observeLanguage(): Flow<String> = settingsStore.language

    override suspend fun setNotificationsEnabled(enabled: Boolean) = settingsStore.setNotificationsEnabled(enabled)
    override suspend fun setSosNotificationsEnabled(enabled: Boolean) = settingsStore.setSosNotificationsEnabled(enabled)
    override suspend fun setHelperNotificationsEnabled(enabled: Boolean) = settingsStore.setHelperNotificationsEnabled(enabled)
    override suspend fun setAiNotificationsEnabled(enabled: Boolean) = settingsStore.setAiNotificationsEnabled(enabled)
    override suspend fun setAiAudioDetectionEnabled(enabled: Boolean) = settingsStore.setAiAudioDetectionEnabled(enabled)
    override suspend fun setAiMovementDetectionEnabled(enabled: Boolean) = settingsStore.setAiMovementDetectionEnabled(enabled)
    override suspend fun setAiSensitivity(sensitivity: AiSensitivity) = settingsStore.setAiSensitivity(sensitivity)
    override suspend fun setAiHelpImproveEnabled(enabled: Boolean) = settingsStore.setAiHelpImproveEnabled(enabled)
    override suspend fun setAiMonitoringEnabled(enabled: Boolean) = aiSettingsStore.setMonitoringEnabled(enabled)
    override suspend fun setThemeMode(mode: AppThemeMode) = settingsStore.setThemeMode(mode)
    override suspend fun setLanguage(languageCode: String) = settingsStore.setLanguage(languageCode)

    override suspend fun getProfile(): Result<UserProfile> = userRepository.getProfile()

    override suspend fun getSecurityInfo(): SecurityInfo {
        val hasJwt = !secureTokenStore.getAccessToken().isNullOrBlank()
        return SecurityInfo(
            hasJwt = hasJwt,
            isSessionActive = hasJwt && authSessionManager.hasSession(),
            isPhoneVerified = userPreferences.isPhoneVerified.first(),
            appVersion = BuildConfig.VERSION_NAME,
            backendUrl = if (BuildConfig.ENABLE_LOGGING) BuildConfig.BASE_URL else "",
        )
    }

    override fun getPermissionStatuses(): PermissionStatuses {
        return PermissionStatuses(
            location = mapLocationStatus(),
            microphone = mapAudioStatus(),
            notifications = mapNotificationStatus(),
            backgroundLocation = mapBackgroundLocationStatus(),
        )
    }

    override fun isBatteryOptimizationDisabled(): Boolean =
        batteryOptimizationManager.isIgnoringBatteryOptimizations()

    override fun openAppSettings() = locationPermissionManager.openAppSettings()

    override fun openBatteryOptimizationSettings() =
        batteryOptimizationManager.openBatteryOptimizationSettings()

    override suspend fun logout() = sessionCleanupManager.performLogout()

    private fun mapLocationStatus(): PermissionDisplayStatus {
        return if (locationPermissionManager.hasLocationPermission()) {
            PermissionDisplayStatus.GRANTED
        } else {
            PermissionDisplayStatus.DENIED
        }
    }

    private fun mapAudioStatus(): PermissionDisplayStatus {
        return when {
            audioPermissionManager.hasRecordAudioPermission() -> PermissionDisplayStatus.GRANTED
            else -> PermissionDisplayStatus.DENIED
        }
    }

    private fun mapNotificationStatus(): PermissionDisplayStatus {
        return when {
            !notificationPermissionManager.requiresRuntimePermission() -> PermissionDisplayStatus.GRANTED
            notificationPermissionManager.hasNotificationPermission() -> PermissionDisplayStatus.GRANTED
            else -> PermissionDisplayStatus.DENIED
        }
    }

    private fun mapBackgroundLocationStatus(): PermissionDisplayStatus {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return if (locationPermissionManager.hasLocationPermission()) {
                PermissionDisplayStatus.GRANTED
            } else {
                PermissionDisplayStatus.NOT_REQUESTED
            }
        }
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_BACKGROUND_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        return when {
            granted -> PermissionDisplayStatus.GRANTED
            locationPermissionManager.hasLocationPermission() -> PermissionDisplayStatus.DENIED
            else -> PermissionDisplayStatus.NOT_REQUESTED
        }
    }
}
