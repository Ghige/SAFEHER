package com.safeher.app.feature.dashboard

import app.cash.turbine.test
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.UserRepository
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
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun loadProfile_success_updatesUiState() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = DashboardViewModel(userRepository)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(sampleProfile, viewModel.uiState.value.profile)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun loadProfile_failure_setsError() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(Exception("Network error"))
        viewModel = DashboardViewModel(userRepository)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals("Network error", viewModel.uiState.value.error)
        assertNull(viewModel.uiState.value.profile)
    }

    @Test
    fun loadProfile_retry_callsRepositoryAgain() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(Exception("Network error")) andThen
            Result.success(sampleProfile)
        viewModel = DashboardViewModel(userRepository)

        viewModel.loadProfile()

        assertNotNull(viewModel.uiState.value.profile)
        coVerify(atLeast = 2) { userRepository.getProfile() }
    }

    @Test
    fun onQuickAction_emitsNavigationEvent() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = DashboardViewModel(userRepository)

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
        viewModel = DashboardViewModel(userRepository)

        assertFalse(viewModel.uiState.value.isOffline)

        onlineFlow.value = false
        assertTrue(viewModel.uiState.value.isOffline)
    }
}
