package com.safeher.app.feature.settings

import app.cash.turbine.test
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.model.PermissionDisplayStatus
import com.safeher.app.domain.model.PermissionStatuses
import com.safeher.app.domain.model.SecurityInfo
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.SettingsRepository
import com.safeher.app.domain.repository.UserRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {

    private val settingsRepository: SettingsRepository = mockk(relaxed = true)
    private val userRepository: UserRepository = mockk()
    private lateinit var viewModel: SettingsViewModel
    private val testDispatcher = UnconfinedTestDispatcher()

    private val sampleProfile = UserProfile(
        id = "uuid-1",
        phoneNumber = "9876543210",
        name = "Jane Doe",
        city = "Mumbai",
        isVerified = true,
    )

    private val securityInfo = SecurityInfo(
        hasJwt = true,
        isSessionActive = true,
        isPhoneVerified = true,
        appVersion = "1.0.0",
        backendUrl = "http://localhost:8000",
    )

    private val permissionStatuses = PermissionStatuses(
        location = PermissionDisplayStatus.GRANTED,
        microphone = PermissionDisplayStatus.DENIED,
        notifications = PermissionDisplayStatus.GRANTED,
        backgroundLocation = PermissionDisplayStatus.NOT_REQUESTED,
    )

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        every { userRepository.observeNetworkStatus() } returns flowOf(true)
        every { settingsRepository.observeNotificationsEnabled() } returns flowOf(true)
        every { settingsRepository.observeSosNotificationsEnabled() } returns flowOf(true)
        every { settingsRepository.observeHelperNotificationsEnabled() } returns flowOf(true)
        every { settingsRepository.observeAiNotificationsEnabled() } returns flowOf(true)
        every { settingsRepository.observeAiMonitoringEnabled() } returns flowOf(false)
        every { settingsRepository.observeAiAudioDetectionEnabled() } returns flowOf(true)
        every { settingsRepository.observeAiMovementDetectionEnabled() } returns flowOf(true)
        every { settingsRepository.observeAiSensitivity() } returns flowOf(AiSensitivity.MEDIUM)
        every { settingsRepository.observeThemeMode() } returns flowOf(AppThemeMode.SYSTEM)
        every { settingsRepository.observeLanguage() } returns flowOf("en")
        coEvery { settingsRepository.getProfile() } returns Result.success(sampleProfile)
        coEvery { settingsRepository.getSecurityInfo() } returns securityInfo
        every { settingsRepository.getPermissionStatuses() } returns permissionStatuses
        every { settingsRepository.isBatteryOptimizationDisabled() } returns true
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun refresh_loadsProfileAndSecurityInfo() = runTest {
        viewModel = SettingsViewModel(settingsRepository, userRepository)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(sampleProfile, viewModel.uiState.value.profile)
        assertEquals(securityInfo, viewModel.uiState.value.securityInfo)
        assertTrue(viewModel.uiState.value.isBatteryOptimizationDisabled)
    }

    @Test
    fun setNotificationsEnabled_persistsViaRepository() = runTest {
        viewModel = SettingsViewModel(settingsRepository, userRepository)

        viewModel.setNotificationsEnabled(false)

        coVerify { settingsRepository.setNotificationsEnabled(false) }
    }

    @Test
    fun setAiMonitoringEnabled_persistsViaRepository() = runTest {
        viewModel = SettingsViewModel(settingsRepository, userRepository)

        viewModel.setAiMonitoringEnabled(true)

        coVerify { settingsRepository.setAiMonitoringEnabled(true) }
    }

    @Test
    fun logout_emitsNavigateToLogin() = runTest {
        viewModel = SettingsViewModel(settingsRepository, userRepository)

        viewModel.events.test {
            viewModel.logout()
            assertEquals(SettingsEvent.NavigateToLogin, awaitItem())
        }

        coVerify { settingsRepository.logout() }
        assertFalse(viewModel.uiState.value.isLoggingOut)
    }

    @Test
    fun refreshPermissions_updatesPermissionStatuses() = runTest {
        val updated = permissionStatuses.copy(microphone = PermissionDisplayStatus.GRANTED)
        every { settingsRepository.getPermissionStatuses() } returns updated andThen updated
        every { settingsRepository.isBatteryOptimizationDisabled() } returns false

        viewModel = SettingsViewModel(settingsRepository, userRepository)
        viewModel.refreshPermissions()

        assertEquals(updated, viewModel.uiState.value.permissionStatuses)
        assertFalse(viewModel.uiState.value.isBatteryOptimizationDisabled)
    }
}
