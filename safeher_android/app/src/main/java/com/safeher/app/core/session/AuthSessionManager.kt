package com.safeher.app.core.session

import com.safeher.app.core.datastore.SecureTokenStore
import com.safeher.app.core.datastore.UserPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthSessionManager @Inject constructor(
    private val secureTokenStore: SecureTokenStore,
    private val userPreferences: UserPreferences,
) {
    private val _sessionExpired = MutableStateFlow(false)
    val sessionExpired: StateFlow<Boolean> = _sessionExpired.asStateFlow()

    suspend fun hasSession(): Boolean = !secureTokenStore.getAccessToken().isNullOrBlank()

    suspend fun logout() {
        secureTokenStore.clear()
        userPreferences.clear()
        _sessionExpired.value = false
    }

    suspend fun onSessionExpired() {
        secureTokenStore.clear()
        _sessionExpired.value = true
    }

    fun clearSessionExpiredFlag() {
        _sessionExpired.value = false
    }
}
