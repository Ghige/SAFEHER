package com.safeher.app.domain.repository

import kotlinx.coroutines.flow.StateFlow

interface AuthRepository {

    val sessionExpired: StateFlow<Boolean>

    suspend fun register(
        phoneNumber: String,
        name: String,
        password: String,
        city: String?,
    ): Result<Unit>

    suspend fun login(phoneNumber: String, password: String): Result<Unit>

    suspend fun sendOtp(phoneNumber: String): Result<String>

    suspend fun verifyOtp(phoneNumber: String, otp: String): Result<String>

    suspend fun logout()

    suspend fun hasValidSession(): Boolean

    suspend fun isPhoneVerified(): Boolean

    suspend fun getStoredPhone(): String?

    fun clearSessionExpiredFlag()
}
