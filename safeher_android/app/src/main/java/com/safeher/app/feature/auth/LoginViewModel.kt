package com.safeher.app.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.domain.repository.AuthRepository
import com.safeher.app.feature.auth.util.AuthValidator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val phone: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val phoneError: String? = null,
    val passwordError: String? = null,
)

sealed interface LoginEvent {
    data object NavigateToHome : LoginEvent
    data class NavigateToOtp(val phone: String) : LoginEvent
}

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<LoginEvent>()
    val events: SharedFlow<LoginEvent> = _events.asSharedFlow()

    fun onPhoneChange(value: String) {
        _uiState.update { it.copy(phone = value, phoneError = null, error = null) }
    }

    fun onPasswordChange(value: String) {
        _uiState.update { it.copy(password = value, passwordError = null, error = null) }
    }

    fun login() {
        val phone = AuthValidator.normalizePhone(_uiState.value.phone)
        val password = _uiState.value.password
        val phoneError = AuthValidator.validatePhone(phone)
        val passwordError = AuthValidator.validatePassword(password)
        if (phoneError != null || passwordError != null) {
            _uiState.update {
                it.copy(phoneError = phoneError, passwordError = passwordError)
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = authRepository.login(phone, password)
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = {
                    val verified = authRepository.isPhoneVerified()
                    if (verified) {
                        _events.emit(LoginEvent.NavigateToHome)
                    } else {
                        _events.emit(LoginEvent.NavigateToOtp(phone))
                    }
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }
}
