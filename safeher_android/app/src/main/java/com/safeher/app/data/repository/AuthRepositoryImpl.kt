package com.safeher.app.data.repository

import com.safeher.app.core.datastore.SecureTokenStore
import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.core.network.SafeHerApi
import com.safeher.app.core.session.AuthSessionManager
import com.safeher.app.data.remote.dto.LoginRequestDto
import com.safeher.app.data.remote.dto.OtpVerifyRequestDto
import com.safeher.app.data.remote.dto.RegisterRequestDto
import com.safeher.app.data.remote.dto.SendOtpRequestDto
import com.safeher.app.domain.repository.AuthRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepositoryImpl @Inject constructor(
    private val api: SafeHerApi,
    private val secureTokenStore: SecureTokenStore,
    private val userPreferences: UserPreferences,
    private val authSessionManager: AuthSessionManager,
    private val moshi: Moshi,
) : AuthRepository {

    override val sessionExpired: StateFlow<Boolean> = authSessionManager.sessionExpired

    override suspend fun register(
        phoneNumber: String,
        name: String,
        password: String,
        city: String?,
    ): Result<Unit> = RepositoryApiCall.execute(moshi) {
        val response = api.register(
            RegisterRequestDto(
                phone_number = phoneNumber.trim(),
                name = name.trim(),
                password = password,
                city = city?.trim()?.takeIf { it.isNotEmpty() },
            ),
        )
        secureTokenStore.saveAccessToken(response.access_token)
        userPreferences.setUserPhone(phoneNumber.trim())
        userPreferences.setPhoneVerified(false)
    }

    override suspend fun login(phoneNumber: String, password: String): Result<Unit> = RepositoryApiCall.execute(moshi) {
        val response = api.login(
            LoginRequestDto(
                phone_number = phoneNumber.trim(),
                password = password,
            ),
        )
        secureTokenStore.saveAccessToken(response.access_token)
        userPreferences.setUserPhone(phoneNumber.trim())
    }

    override suspend fun sendOtp(phoneNumber: String): Result<String> = RepositoryApiCall.execute(moshi) {
        api.sendOtp(SendOtpRequestDto(phone_number = phoneNumber.trim())).message
    }

    override suspend fun verifyOtp(phoneNumber: String, otp: String): Result<String> = RepositoryApiCall.execute(moshi) {
        val message = api.verifyOtp(
            OtpVerifyRequestDto(
                phone_number = phoneNumber.trim(),
                otp = otp.trim(),
            ),
        ).message
        userPreferences.setPhoneVerified(true)
        message
    }

    override suspend fun logout() {
        authSessionManager.logout()
    }

    override suspend fun hasValidSession(): Boolean = authSessionManager.hasSession()

    override suspend fun isPhoneVerified(): Boolean =
        userPreferences.isPhoneVerified.first()

    override suspend fun getStoredPhone(): String? = userPreferences.userPhone.first()

    override fun clearSessionExpiredFlag() {
        authSessionManager.clearSessionExpiredFlag()
    }
}
