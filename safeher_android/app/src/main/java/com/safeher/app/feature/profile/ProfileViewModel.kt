package com.safeher.app.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.domain.repository.AuthRepository
import com.safeher.app.domain.repository.UserRepository
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

sealed interface ProfileEvent {
    data object NavigateToLogin : ProfileEvent
}

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val userRepository: UserRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ProfileUiState())
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<ProfileEvent>()
    val events: SharedFlow<ProfileEvent> = _events.asSharedFlow()

    init {
        observeNetwork()
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null, isEmpty = false) }
            val result = userRepository.getProfile()
            result.fold(
                onSuccess = { profile ->
                    _uiState.update {
                        it.copy(isLoading = false, profile = profile, error = null)
                    }
                },
                onFailure = { error ->
                    val message = error.message.orEmpty()
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            error = message,
                            isEmpty = message.contains("incomplete", ignoreCase = true),
                        )
                    }
                },
            )
        }
    }

    fun logout() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoggingOut = true) }
            _events.emit(ProfileEvent.NavigateToLogin)
            _uiState.update { it.copy(isLoggingOut = false) }
        }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            userRepository.observeNetworkStatus().collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }
}
