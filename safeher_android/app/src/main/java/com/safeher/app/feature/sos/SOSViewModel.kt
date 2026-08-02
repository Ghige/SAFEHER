package com.safeher.app.feature.sos

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.feature.sos.util.SosLocationHelper
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
class SOSViewModel @Inject constructor(
    private val alertRepository: AlertRepository,
    private val alertSessionManager: AlertSessionManager,
    private val networkMonitor: NetworkMonitor,
    private val locationHelper: SosLocationHelper,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SOSUiState())
    val uiState: StateFlow<SOSUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<SOSEvent>()
    val events: SharedFlow<SOSEvent> = _events.asSharedFlow()

    private var countdownJob: Job? = null

    init {
        observeNetwork()
        observeSession()
    }

    fun restoreActiveAlert() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            alertSessionManager.restoreActiveAlert()
            val alert = alertSessionManager.activeAlert.value
            _uiState.update { it.copy(isLoading = false, activeAlert = alert) }
            if (alert?.isOngoing == true) {
                alertSessionManager.startHeartbeat(alert.id, viewModelScope)
                _events.emit(SOSEvent.NavigateToActive)
            }
        }
    }

    fun onSosButtonClick() {
        if (alertSessionManager.activeAlert.value?.isOngoing == true) {
            viewModelScope.launch { _events.emit(SOSEvent.NavigateToActive) }
            return
        }
        viewModelScope.launch { _events.emit(SOSEvent.NavigateToCountdown) }
    }

    fun startCountdown() {
        countdownJob?.cancel()
        countdownJob = viewModelScope.launch {
            for (seconds in COUNTDOWN_SECONDS downTo 1) {
                _uiState.update { it.copy(countdownSeconds = seconds, error = null) }
                delay(1_000)
            }
            _uiState.update { it.copy(countdownSeconds = null) }
            triggerSos()
        }
    }

    fun cancelCountdown() {
        countdownJob?.cancel()
        countdownJob = null
        _uiState.update { it.copy(countdownSeconds = null, error = null) }
        viewModelScope.launch { _events.emit(SOSEvent.NavigateBack) }
    }

    fun triggerSos() {
        viewModelScope.launch {
            _uiState.update { it.copy(isTriggering = true, error = null) }
            val coords = locationHelper.getCurrentCoordinates()
            val result = alertRepository.triggerAlert(
                latitude = coords?.latitude,
                longitude = coords?.longitude,
            )
            _uiState.update { it.copy(isTriggering = false) }
            result.fold(
                onSuccess = { alert ->
                    alertSessionManager.setActiveAlert(alert)
                    alertSessionManager.startHeartbeat(alert.id, viewModelScope)
                    _uiState.update { it.copy(activeAlert = alert) }
                    _events.emit(SOSEvent.NavigateToActive)
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                    _events.emit(SOSEvent.NavigateBack)
                },
            )
        }
    }

    fun requestCancelActiveAlert() {
        _uiState.update { it.copy(showCancelDialog = true) }
    }

    fun dismissCancelDialog() {
        _uiState.update { it.copy(showCancelDialog = false) }
    }

    fun confirmCancelActiveAlert() {
        val alertId = alertSessionManager.activeAlert.value?.id ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, showCancelDialog = false) }
            val result = alertRepository.cancelAlert(alertId)
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = {
                    alertSessionManager.clearActiveAlert()
                    _uiState.update { it.copy(activeAlert = null) }
                    _events.emit(SOSEvent.NavigateBack)
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }

    fun navigateToHistory() {
        viewModelScope.launch { _events.emit(SOSEvent.NavigateToHistory) }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }

    private fun observeSession() {
        viewModelScope.launch {
            alertSessionManager.activeAlert.collect { alert ->
                _uiState.update { it.copy(activeAlert = alert) }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        countdownJob?.cancel()
    }

    companion object {
        const val COUNTDOWN_SECONDS = 5
    }
}
