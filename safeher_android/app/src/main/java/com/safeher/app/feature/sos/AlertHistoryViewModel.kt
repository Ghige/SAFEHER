package com.safeher.app.feature.sos

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AlertHistoryUiState(
    val isLoading: Boolean = true,
    val history: List<SafetyAlert> = emptyList(),
    val error: String? = null,
    val isOffline: Boolean = false,
)

@HiltViewModel
class AlertHistoryViewModel @Inject constructor(
    private val alertRepository: AlertRepository,
    private val networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AlertHistoryUiState())
    val uiState: StateFlow<AlertHistoryUiState> = _uiState.asStateFlow()

    init {
        observeNetwork()
        loadHistory()
    }

    fun loadHistory() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = alertRepository.getHistory()
            result.fold(
                onSuccess = { history ->
                    _uiState.update { it.copy(isLoading = false, history = history) }
                },
                onFailure = { error ->
                    _uiState.update { it.copy(isLoading = false, error = error.message) }
                },
            )
        }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }
}
