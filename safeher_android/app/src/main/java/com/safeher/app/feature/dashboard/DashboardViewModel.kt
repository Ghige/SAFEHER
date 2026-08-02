package com.safeher.app.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val userRepository: UserRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DashboardEvent>()
    val events: SharedFlow<DashboardEvent> = _events.asSharedFlow()

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
                        it.copy(
                            isLoading = false,
                            profile = profile,
                            error = null,
                            isEmpty = false,
                        )
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

    fun onQuickAction(feature: QuickActionFeature) {
        viewModelScope.launch {
            _events.emit(DashboardEvent.NavigateToComingSoon(feature.routeKey))
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
