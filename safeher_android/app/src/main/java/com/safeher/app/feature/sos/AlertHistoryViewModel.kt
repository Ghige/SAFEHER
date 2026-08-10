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
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            history = history,
                            filteredHistory = applyFilter(history, it.selectedFilter),
                        )
                    }
                },
                onFailure = { error ->
                    _uiState.update { it.copy(isLoading = false, error = error.message) }
                },
            )
        }
    }

    fun setFilter(filter: AlertHistoryFilter) {
        _uiState.update {
            it.copy(
                selectedFilter = filter,
                filteredHistory = applyFilter(it.history, filter),
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

    private fun applyFilter(
        history: List<SafetyAlert>,
        filter: AlertHistoryFilter,
    ): List<SafetyAlert> = when (filter) {
        AlertHistoryFilter.ALL -> history
        AlertHistoryFilter.SOS -> history.filter {
            it.triggerType.contains("manual", ignoreCase = true) ||
                it.triggerType.contains("sos", ignoreCase = true)
        }
        AlertHistoryFilter.AI -> history.filter {
            it.triggerType.contains("ai", ignoreCase = true) ||
                it.triggerType.contains("audio", ignoreCase = true)
        }
        AlertHistoryFilter.LOCATION -> history.filter {
            it.triggerType.contains("location", ignoreCase = true) ||
                (it.latitude != null && it.longitude != null)
        }
    }
}
