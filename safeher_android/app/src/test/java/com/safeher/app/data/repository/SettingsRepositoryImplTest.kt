package com.safeher.app.data.repository

import android.content.Context
import com.safeher.app.core.datastore.AiSettingsStore
import com.safeher.app.core.datastore.SecureTokenStore
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.session.AuthSessionManager
import com.safeher.app.core.session.SessionCleanupManager
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.model.PermissionDisplayStatus
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.services.AudioPermissionManager
import com.safeher.app.services.BatteryOptimizationManager
import com.safeher.app.services.LocationPermissionManager
import com.safeher.app.services.NotificationPermissionManager
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SettingsRepositoryImplTest {

    private val context: Context = mockk(relaxed = true)
    private val settingsStore: SettingsStore = mockk(relaxed = true)
    private val aiSettingsStore: AiSettingsStore = mockk(relaxed = true)
    private val userRepository: UserRepository = mockk()
    private val secureTokenStore: SecureTokenStore = mockk()
    private val authSessionManager: AuthSessionManager = mockk()
    private val sessionCleanupManager: SessionCleanupManager = mockk(relaxed = true)
    private val userPreferences: UserPreferences = mockk()
    private val locationPermissionManager: LocationPermissionManager = mockk()
    private val audioPermissionManager: AudioPermissionManager = mockk()
    private val notificationPermissionManager: NotificationPermissionManager = mockk()
    private val batteryOptimizationManager: BatteryOptimizationManager = mockk()

    private lateinit var repository: SettingsRepositoryImpl

    private val sampleProfile = UserProfile(
        id = "uuid-1",
        phoneNumber = "9876543210",
        name = "Jane Doe",
        city = "Mumbai",
        isVerified = true,
    )

    @Before
    fun setup() {
        every { settingsStore.notificationsEnabled } returns flowOf(true)
        every { settingsStore.sosNotificationsEnabled } returns flowOf(true)
        every { settingsStore.helperNotificationsEnabled } returns flowOf(true)
        every { settingsStore.aiNotificationsEnabled } returns flowOf(true)
        every { settingsStore.aiAudioDetectionEnabled } returns flowOf(true)
        every { settingsStore.aiMovementDetectionEnabled } returns flowOf(true)
        every { settingsStore.aiSensitivity } returns flowOf(AiSensitivity.MEDIUM)
        every { settingsStore.themeMode } returns flowOf(AppThemeMode.SYSTEM)
        every { settingsStore.language } returns flowOf("en")
        every { aiSettingsStore.monitoringEnabled } returns flowOf(false)
        every { locationPermissionManager.hasLocationPermission() } returns true
        every { audioPermissionManager.hasRecordAudioPermission() } returns false
        every { notificationPermissionManager.requiresRuntimePermission() } returns false
        every { batteryOptimizationManager.isIgnoringBatteryOptimizations() } returns true

        repository = SettingsRepositoryImpl(
            context = context,
            settingsStore = settingsStore,
            aiSettingsStore = aiSettingsStore,
            userRepository = userRepository,
            secureTokenStore = secureTokenStore,
            authSessionManager = authSessionManager,
            sessionCleanupManager = sessionCleanupManager,
            userPreferences = userPreferences,
            locationPermissionManager = locationPermissionManager,
            audioPermissionManager = audioPermissionManager,
            notificationPermissionManager = notificationPermissionManager,
            batteryOptimizationManager = batteryOptimizationManager,
        )
    }

    @Test
    fun getProfile_delegatesToUserRepository() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)

        val result = repository.getProfile()

        assertTrue(result.isSuccess)
        assertEquals(sampleProfile, result.getOrNull())
    }

    @Test
    fun getSecurityInfo_reflectsTokenAndSession() = runTest {
        coEvery { secureTokenStore.getAccessToken() } returns "jwt-token"
        coEvery { authSessionManager.hasSession() } returns true
        coEvery { userPreferences.isPhoneVerified } returns flowOf(true)

        val info = repository.getSecurityInfo()

        assertTrue(info.hasJwt)
        assertTrue(info.isSessionActive)
        assertTrue(info.isPhoneVerified)
    }

    @Test
    fun getSecurityInfo_missingJwt() = runTest {
        coEvery { secureTokenStore.getAccessToken() } returns null
        coEvery { authSessionManager.hasSession() } returns false
        coEvery { userPreferences.isPhoneVerified } returns flowOf(false)

        val info = repository.getSecurityInfo()

        assertFalse(info.hasJwt)
        assertFalse(info.isSessionActive)
        assertFalse(info.isPhoneVerified)
    }

    @Test
    fun getPermissionStatuses_mapsGrantedAndDenied() {
        every { locationPermissionManager.hasLocationPermission() } returns true
        every { audioPermissionManager.hasRecordAudioPermission() } returns false

        val statuses = repository.getPermissionStatuses()

        assertEquals(PermissionDisplayStatus.GRANTED, statuses.location)
        assertEquals(PermissionDisplayStatus.DENIED, statuses.microphone)
        assertEquals(PermissionDisplayStatus.GRANTED, statuses.notifications)
    }

    @Test
    fun setNotificationsEnabled_persistsToStore() = runTest {
        repository.setNotificationsEnabled(false)

        coVerify { settingsStore.setNotificationsEnabled(false) }
    }

    @Test
    fun setAiMonitoringEnabled_delegatesToAiSettingsStore() = runTest {
        repository.setAiMonitoringEnabled(true)

        coVerify { aiSettingsStore.setMonitoringEnabled(true) }
    }

    @Test
    fun logout_usesSessionCleanupManager() = runTest {
        coEvery { sessionCleanupManager.performLogout() } returns Unit

        repository.logout()

        coVerify { sessionCleanupManager.performLogout() }
    }

    @Test
    fun openAppSettings_delegatesToLocationPermissionManager() {
        every { locationPermissionManager.openAppSettings() } returns Unit

        repository.openAppSettings()

        verify(exactly = 1) { locationPermissionManager.openAppSettings() }
    }
}
