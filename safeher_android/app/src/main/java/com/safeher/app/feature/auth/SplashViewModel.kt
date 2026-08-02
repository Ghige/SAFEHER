package com.safeher.app.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.domain.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface SplashDestination {
    data object Onboarding : SplashDestination
    data object Login : SplashDestination
    data object Home : SplashDestination
    data class Otp(val phone: String) : SplashDestination
    data object SessionExpired : SplashDestination
}

@HiltViewModel
class SplashViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val userPreferences: UserPreferences,
) : ViewModel() {

    private val _destination = MutableStateFlow<SplashDestination?>(null)
    val destination: StateFlow<SplashDestination?> = _destination.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    fun resolveStartDestination() {
        viewModelScope.launch {
            _isLoading.value = true
            val dest = when {
                authRepository.sessionExpired.value -> SplashDestination.SessionExpired
                authRepository.hasValidSession() -> {
                    val verified = authRepository.isPhoneVerified()
                    val phone = authRepository.getStoredPhone()
                    when {
                        !verified && !phone.isNullOrBlank() -> SplashDestination.Otp(phone)
                        else -> SplashDestination.Home
                    }
                }
                !userPreferences.onboardingCompleted.first() -> SplashDestination.Onboarding
                else -> SplashDestination.Login
            }
            _isLoading.value = false
            _destination.value = dest
        }
    }
}
