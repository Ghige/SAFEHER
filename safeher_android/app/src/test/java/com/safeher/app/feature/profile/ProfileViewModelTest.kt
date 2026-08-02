package com.safeher.app.feature.profile

import app.cash.turbine.test
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.AuthRepository
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
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ProfileViewModelTest {

    private val userRepository: UserRepository = mockk()
    private val authRepository: AuthRepository = mockk(relaxed = true)
    private lateinit var viewModel: ProfileViewModel
    private val testDispatcher = UnconfinedTestDispatcher()

    private val sampleProfile = UserProfile(
        id = "uuid-1",
        phoneNumber = "9876543210",
        name = "Jane Doe",
        city = "Mumbai",
        isVerified = false,
    )

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        every { userRepository.observeNetworkStatus() } returns flowOf(true)
        every { authRepository.sessionExpired } returns MutableStateFlow(false)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun loadProfile_success_updatesUiState() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = ProfileViewModel(userRepository, authRepository)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(sampleProfile, viewModel.uiState.value.profile)
    }

    @Test
    fun loadProfile_offlineError_setsError() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(
            Exception("You are offline. Connect to the internet and try again."),
        )
        viewModel = ProfileViewModel(userRepository, authRepository)

        assertEquals(
            "You are offline. Connect to the internet and try again.",
            viewModel.uiState.value.error,
        )
    }

    @Test
    fun logout_emitsNavigateToLogin() = runTest {
        coEvery { userRepository.getProfile() } returns Result.success(sampleProfile)
        viewModel = ProfileViewModel(userRepository, authRepository)

        viewModel.events.test {
            viewModel.logout()
            assertEquals(ProfileEvent.NavigateToLogin, awaitItem())
        }

        coVerify(exactly = 0) { authRepository.logout() }
        assertFalse(viewModel.uiState.value.isLoggingOut)
    }

    @Test
    fun loadProfile_retry_succeeds() = runTest {
        coEvery { userRepository.getProfile() } returns Result.failure(Exception("Network error")) andThen
            Result.success(sampleProfile)
        viewModel = ProfileViewModel(userRepository, authRepository)

        viewModel.loadProfile()

        assertNull(viewModel.uiState.value.error)
        assertEquals(sampleProfile, viewModel.uiState.value.profile)
    }
}
