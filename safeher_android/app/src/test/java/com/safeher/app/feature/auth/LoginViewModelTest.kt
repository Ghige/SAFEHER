package com.safeher.app.feature.auth

import app.cash.turbine.test
import com.safeher.app.domain.repository.AuthRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    private val authRepository: AuthRepository = mockk(relaxed = true)
    private lateinit var viewModel: LoginViewModel
    private val testDispatcher = UnconfinedTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        coEvery { authRepository.sessionExpired } returns MutableStateFlow(false)
        viewModel = LoginViewModel(authRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun login_withInvalidPhone_setsPhoneError() = runTest {
        viewModel.onPhoneChange("123")
        viewModel.onPasswordChange("password123")
        viewModel.login()

        assertEquals("Enter a valid 10–15 digit phone number", viewModel.uiState.value.phoneError)
        coVerify(exactly = 0) { authRepository.login(any(), any()) }
    }

    @Test
    fun login_success_navigatesToHomeWhenVerified() = runTest {
        coEvery { authRepository.login(any(), any()) } returns Result.success(Unit)
        coEvery { authRepository.isPhoneVerified() } returns true

        viewModel.onPhoneChange("9876543210")
        viewModel.onPasswordChange("password123")

        viewModel.events.test {
            viewModel.login()
            assertEquals(LoginEvent.NavigateToHome, awaitItem())
        }

        assertNull(viewModel.uiState.value.error)
        coVerify { authRepository.login("9876543210", "password123") }
    }

    @Test
    fun login_success_navigatesToOtpWhenNotVerified() = runTest {
        coEvery { authRepository.login(any(), any()) } returns Result.success(Unit)
        coEvery { authRepository.isPhoneVerified() } returns false

        viewModel.onPhoneChange("9876543210")
        viewModel.onPasswordChange("password123")

        viewModel.events.test {
            viewModel.login()
            assertEquals(LoginEvent.NavigateToOtp("9876543210"), awaitItem())
        }
    }

    @Test
    fun login_failure_setsError() = runTest {
        coEvery { authRepository.login(any(), any()) } returns Result.failure(Exception("Invalid credentials"))

        viewModel.onPhoneChange("9876543210")
        viewModel.onPasswordChange("password123")
        viewModel.login()

        assertEquals("Invalid credentials", viewModel.uiState.value.error)
    }
}
