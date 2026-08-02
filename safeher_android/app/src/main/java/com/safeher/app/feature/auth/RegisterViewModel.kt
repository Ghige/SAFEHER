package com.safeher.app.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.domain.repository.AuthRepository
import com.safeher.app.feature.auth.util.AuthValidator
import com.safeher.app.feature.auth.util.PasswordStrength
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

data class RegisterUiState(
    val phone: String = "",
    val name: String = "",
    val password: String = "",
    val city: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val phoneError: String? = null,
    val nameError: String? = null,
    val passwordError: String? = null,
    val passwordStrength: PasswordStrength = PasswordStrength.WEAK,
)

sealed interface RegisterEvent {
    data class NavigateToOtp(val phone: String) : RegisterEvent
}

@HiltViewModel
class RegisterViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(RegisterUiState())
    val uiState: StateFlow<RegisterUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<RegisterEvent>()
    val events: SharedFlow<RegisterEvent> = _events.asSharedFlow()

    fun onPhoneChange(value: String) {
        _uiState.update { it.copy(phone = value, phoneError = null, error = null) }
    }

    fun onNameChange(value: String) {
        _uiState.update { it.copy(name = value, nameError = null, error = null) }
    }

    fun onPasswordChange(value: String) {
        _uiState.update {
            it.copy(
                password = value,
                passwordError = null,
                error = null,
                passwordStrength = AuthValidator.passwordStrength(value),
            )
        }
    }

    fun onCityChange(value: String) {
        _uiState.update { it.copy(city = value, error = null) }
    }

    fun register() {
        val phone = AuthValidator.normalizePhone(_uiState.value.phone)
        val name = _uiState.value.name
        val password = _uiState.value.password
        val city = _uiState.value.city

        val phoneError = AuthValidator.validatePhone(phone)
        val nameError = AuthValidator.validateName(name)
        val passwordError = AuthValidator.validatePassword(password)
        if (phoneError != null || nameError != null || passwordError != null) {
            _uiState.update {
                it.copy(
                    phoneError = phoneError,
                    nameError = nameError,
                    passwordError = passwordError,
                )
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = authRepository.register(
                phoneNumber = phone,
                name = name,
                password = password,
                city = city.takeIf { it.isNotBlank() },
            )
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = { _events.emit(RegisterEvent.NavigateToOtp(phone)) },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }
}
