package com.safeher.app.feature.dashboard

import app.cash.turbine.test
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.ContactsRepository
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.LocationTrackingService
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DashboardViewModelTest {

    private val userRepository: UserRepository = mockk()
    private val contactsRepository: ContactsRepository = mockk(relaxed = true)
    private val settingsStore: SettingsStore = mockk(relaxed = true)
    private val aiMonitoringCoordinator: AiMonitoringCoordinator = mockk(relaxed = true)
    private val locationTrackingService: LocationTrackingService = mockk(relaxed = true)
    private lateinit var viewModel: DashboardViewModel
    private val testDispatcher = UnconfinedTestDispatcher()

    private val sampleProfile = UserProfile(
        id = "uuid-1",
        phoneNumber = "9876543210",
        name = "Jane Doe",
        city = "Mumbai",
        isVerified = true,
    )

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        every { userRepository.observeNetworkStatus() } returns flowOf(true)
        every { settingsStore.aiAudioDetectionEnabled } returns flowOf(true)
        every { aiMonitoringCoordinator.isMonitoring } returns flowOf(false)
        every { aiMonitoringCoordinator.riskAssessment } returns flowOf(null)
        every { locationTrackingService.isTracking } returns flowOf(false)
        coEvery { contactsRepository.getContacts() } returns Result.success(emptyList())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel() = DashboardViewModel(
        userRepository = userRepository,
        contactsRepository = contactsRepository,
        settingsStore = settingsStore,
        aiMonitoringCoordinator = aiMonitoringCoordinator,
        locationTrackingService = locationTrackingService,
    )

    @Test
    fun loadProfile_success_updatesUiState() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = createViewModel()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(sampleProfile, viewModel.uiState.value.profile)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun loadProfile_failure_setsError() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(Exception("Network error"))
        viewModel = createViewModel()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals("Network error", viewModel.uiState.value.error)
        assertNull(viewModel.uiState.value.profile)
    }

    @Test
    fun loadProfile_retry_callsRepositoryAgain() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(Exception("Network error")) andThen
            Result.success(sampleProfile)
        viewModel = createViewModel()

        viewModel.loadProfile()

        assertNotNull(viewModel.uiState.value.profile)
        coVerify(atLeast = 2) { userRepository.getProfile() }
    }

    @Test
    fun onQuickAction_emitsNavigationEvent() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = createViewModel()

        viewModel.events.test {
            viewModel.onQuickAction(QuickActionFeature.SOS)
            assertEquals(DashboardEvent.NavigateToComingSoon("sos"), awaitItem())
        }
    }

    @Test
    fun observeNetwork_offlineUpdatesState() = runTest {
        val onlineFlow = MutableStateFlow(true)
        every { userRepository.observeNetworkStatus() } returns onlineFlow
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = createViewModel()

        assertFalse(viewModel.uiState.value.isOffline)

        onlineFlow.value = false
        assertTrue(viewModel.uiState.value.isOffline)
    }
}
