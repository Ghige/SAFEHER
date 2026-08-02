package com.safeher.app.data.repository

import com.safeher.app.core.datastore.SecureTokenStore
import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.network.SafeHerApi
import com.safeher.app.core.session.AuthSessionManager
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AuthRepositoryImplTest {

    private val api: SafeHerApi = mockk()
    private val secureTokenStore: SecureTokenStore = mockk(relaxed = true)
    private val userPreferences: UserPreferences = mockk(relaxed = true)
    private val authSessionManager: AuthSessionManager = mockk(relaxed = true)
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: AuthRepositoryImpl

    @Before
    fun setup() {
        coEvery { authSessionManager.sessionExpired } returns MutableStateFlow(false)
        repository = AuthRepositoryImpl(
            api = api,
            secureTokenStore = secureTokenStore,
            userPreferences = userPreferences,
            authSessionManager = authSessionManager,
            moshi = moshi,
        )
    }

    @Test
    fun login_savesToken() = runTest {
        coEvery { api.login(any()) } returns com.safeher.app.data.remote.dto.TokenResponseDto(
            access_token = "jwt-token",
        )

        val result = repository.login("9876543210", "secret123")

        assertTrue(result.isSuccess)
        coVerify { secureTokenStore.saveAccessToken("jwt-token") }
        coVerify { userPreferences.setUserPhone("9876543210") }
    }

    @Test
    fun register_savesTokenAndMarksUnverified() = runTest {
        coEvery { api.register(any()) } returns com.safeher.app.data.remote.dto.TokenResponseDto(
            access_token = "jwt-token",
        )

        val result = repository.register("9876543210", "Jane", "secret123", "Mumbai")

        assertTrue(result.isSuccess)
        coVerify { secureTokenStore.saveAccessToken("jwt-token") }
        coVerify { userPreferences.setPhoneVerified(false) }
    }

    @Test
    fun verifyOtp_marksPhoneVerified() = runTest {
        coEvery { api.verifyOtp(any()) } returns com.safeher.app.data.remote.dto.MessageResponseDto(
            message = "Phone number verified successfully",
        )

        val result = repository.verifyOtp("9876543210", "123456")

        assertTrue(result.isSuccess)
        assertEquals("Phone number verified successfully", result.getOrNull())
        coVerify { userPreferences.setPhoneVerified(true) }
    }

    @Test
    fun sendOtp_returnsMessage() = runTest {
        coEvery { api.sendOtp(any()) } returns com.safeher.app.data.remote.dto.MessageResponseDto(
            message = "OTP sent successfully",
        )

        val result = repository.sendOtp("9876543210")

        assertTrue(result.isSuccess)
        assertEquals("OTP sent successfully", result.getOrNull())
    }

    @Test
    fun logout_delegatesToSessionManager() = runTest {
        repository.logout()
        coVerify { authSessionManager.logout() }
    }
}
