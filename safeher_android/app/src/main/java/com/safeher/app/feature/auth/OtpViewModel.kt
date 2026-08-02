package com.safeher.app.feature.auth

import androidx.lifecycle.SavedStateHandle
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

data class OtpUiState(
    val phone: String = "",
    val otp: String = "",
    val isLoading: Boolean = false,
    val isResending: Boolean = false,
    val error: String? = null,
    val otpError: String? = null,
    val successMessage: String? = null,
)

sealed interface OtpEvent {
    data object NavigateToHome : OtpEvent
}

@HiltViewModel
class OtpViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val phoneArg: String = savedStateHandle.get<String>("phone").orEmpty()

    private val _uiState = MutableStateFlow(OtpUiState(phone = phoneArg))
    val uiState: StateFlow<OtpUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<OtpEvent>()
    val events: SharedFlow<OtpEvent> = _events.asSharedFlow()

    fun onOtpChange(value: String) {
        val digits = value.filter { it.isDigit() }.take(6)
        _uiState.update { it.copy(otp = digits, otpError = null, error = null) }
        if (digits.length == 6) {
            verifyOtp()
        }
    }

    fun verifyOtp() {
        val phone = _uiState.value.phone
        val otp = _uiState.value.otp
        val otpError = AuthValidator.validateOtp(otp)
        if (otpError != null) {
            _uiState.update { it.copy(otpError = otpError) }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = authRepository.verifyOtp(phone, otp)
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = { message ->
                    _uiState.update { it.copy(successMessage = message) }
                    _events.emit(OtpEvent.NavigateToHome)
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }

    fun resendOtp() {
        val phone = _uiState.value.phone
        viewModelScope.launch {
            _uiState.update { it.copy(isResending = true, error = null) }
            val result = authRepository.sendOtp(phone)
            _uiState.update { it.copy(isResending = false) }
            result.fold(
                onSuccess = { message ->
                    _uiState.update { it.copy(successMessage = message, otp = "") }
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }
}
