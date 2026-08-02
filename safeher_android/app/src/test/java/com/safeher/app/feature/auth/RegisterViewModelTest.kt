package com.safeher.app.feature.auth

import app.cash.turbine.test
import com.safeher.app.domain.repository.AuthRepository
import com.safeher.app.feature.auth.util.PasswordStrength
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
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RegisterViewModelTest {

    private val authRepository: AuthRepository = mockk(relaxed = true)
    private lateinit var viewModel: RegisterViewModel
    private val testDispatcher = UnconfinedTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        coEvery { authRepository.sessionExpired } returns MutableStateFlow(false)
        viewModel = RegisterViewModel(authRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun register_withMissingName_setsNameError() = runTest {
        viewModel.onPhoneChange("9876543210")
        viewModel.onPasswordChange("secret123")
        viewModel.register()

        assertEquals("Name is required", viewModel.uiState.value.nameError)
        coVerify(exactly = 0) { authRepository.register(any(), any(), any(), any()) }
    }

    @Test
    fun onPasswordChange_updatesStrength() {
        viewModel.onPasswordChange("abc")
        assertEquals(PasswordStrength.WEAK, viewModel.uiState.value.passwordStrength)

        viewModel.onPasswordChange("Secret12345")
        assertEquals(PasswordStrength.STRONG, viewModel.uiState.value.passwordStrength)
    }

    @Test
    fun register_success_navigatesToOtp() = runTest {
        coEvery {
            authRepository.register(any(), any(), any(), any())
        } returns Result.success(Unit)

        viewModel.onPhoneChange("9876543210")
        viewModel.onNameChange("Jane Doe")
        viewModel.onPasswordChange("secret123")
        viewModel.onCityChange("Mumbai")

        viewModel.events.test {
            viewModel.register()
            assertEquals(RegisterEvent.NavigateToOtp("9876543210"), awaitItem())
        }

        coVerify {
            authRepository.register("9876543210", "Jane Doe", "secret123", "Mumbai")
        }
    }

    @Test
    fun register_failure_setsError() = runTest {
        coEvery {
            authRepository.register(any(), any(), any(), any())
        } returns Result.failure(Exception("Phone number already registered"))

        viewModel.onPhoneChange("9876543210")
        viewModel.onNameChange("Jane Doe")
        viewModel.onPasswordChange("secret123")
        viewModel.register()

        assertEquals("Phone number already registered", viewModel.uiState.value.error)
    }
}
