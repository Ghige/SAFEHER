package com.safeher.app.feature.sos

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.data.repository.OfflineSosQueuedException
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.feature.sos.util.SosLocationHelper
import com.safeher.app.feature.sos.util.SosPreflightChecker
import com.safeher.app.services.ApplicationCoroutineScope
import com.safeher.app.services.BatteryOptimizationManager
import com.safeher.app.services.LocationPermissionManager
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
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class SOSViewModel @Inject constructor(
    private val alertRepository: AlertRepository,
    private val alertSessionManager: AlertSessionManager,
    private val networkMonitor: NetworkMonitor,
    private val locationHelper: SosLocationHelper,
    private val preflightChecker: SosPreflightChecker,
    private val locationPermissionManager: LocationPermissionManager,
    private val batteryOptimizationManager: BatteryOptimizationManager,
    private val applicationScope: ApplicationCoroutineScope,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SOSUiState())
    val uiState: StateFlow<SOSUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<SOSEvent>()
    val events: SharedFlow<SOSEvent> = _events.asSharedFlow()

    private var countdownJob: Job? = null
    private var navigatedToActiveAlertId: String? = null

    init {
        observeNetwork()
        observeSession()
        observeHeartbeatWarning()
        observePendingSos()
        refreshPreflight()
    }

    fun refreshPreflight() {
        _uiState.update { it.copy(preflight = preflightChecker.evaluate()) }
    }

    fun openLocationSettings() = locationPermissionManager.openLocationSettings()

    fun openAppSettings() = locationPermissionManager.openAppSettings()

    fun openBatterySettings() = batteryOptimizationManager.openBatteryOptimizationSettings()

    fun restoreActiveAlert() {
        syncActiveAlertUi()
    }

    /** Syncs UI from session state restored in [AlertSessionManager] at app startup. */
    fun syncActiveAlertUi() {
        viewModelScope.launch {
            alertSessionManager.awaitRestoreAttempt()
            val alert = alertSessionManager.activeAlert.value
            Timber.d(
                "SOSViewModel.syncActiveAlertUi alert=%s status=%s ongoing=%s",
                alert?.id,
                alert?.status,
                alert?.isOngoing,
            )
            _uiState.update { it.copy(isLoading = false, activeAlert = alert) }
            maybeNavigateToActive(alert)
        }
    }

    private fun maybeNavigateToActive(alert: SafetyAlert?) {
        if (alert?.isOngoing == true && navigatedToActiveAlertId != alert.id) {
            navigatedToActiveAlertId = alert.id
            viewModelScope.launch {
                Timber.d("SOSViewModel: emit NavigateToActive alertId=%s", alert.id)
                _events.emit(SOSEvent.NavigateToActive)
            }
        }
        if (alert == null || !alert.isOngoing) {
            navigatedToActiveAlertId = null
        }
    }

    fun onSosButtonClick() {
        refreshPreflight()
        if (alertSessionManager.activeAlert.value?.isOngoing == true) {
            viewModelScope.launch { _events.emit(SOSEvent.NavigateToActive) }
            return
        }
        viewModelScope.launch { _events.emit(SOSEvent.NavigateToCountdown) }
    }

    fun startCountdown() {
        refreshPreflight()
        val locationAvailable = _uiState.value.preflight?.locationAvailable == true
        _uiState.update { it.copy(showLocationWarning = !locationAvailable) }
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
        _uiState.update { it.copy(countdownSeconds = null, error = null, showLocationWarning = false) }
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
            _uiState.update { it.copy(isTriggering = false, showLocationWarning = false) }
            result.fold(
                onSuccess = { alert ->
                    alertSessionManager.setActiveAlert(alert)
                    alertSessionManager.startHeartbeat(alert.id, applicationScope.scope)
                    _uiState.update {
                        it.copy(
                            activeAlert = alert,
                            whatsappWarning = if (alert.whatsappAllDelivered == false) {
                                WHATSAPP_DELIVERY_WARNING
                            } else {
                                null
                            },
                        )
                    }
                    maybeNavigateToActive(alert)
                },
                onFailure = { error ->
                    if (error is OfflineSosQueuedException) {
                        _uiState.update {
                            it.copy(
                                error = null,
                                hasPendingSos = true,
                                queuedMessage = OfflineSosQueuedException.MESSAGE,
                            )
                        }
                        _events.emit(SOSEvent.NavigateBack)
                    } else {
                        _uiState.update { it.copy(error = error.message) }
                        _events.emit(SOSEvent.NavigateBack)
                    }
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
                _uiState.update {
                    it.copy(
                        activeAlert = alert,
                        hasPendingSos = if (alert?.isOngoing == true) false else it.hasPendingSos,
                        queuedMessage = if (alert?.isOngoing == true) null else it.queuedMessage,
                    )
                }
                if (alert?.isOngoing == true) {
                    maybeNavigateToActive(alert)
                }
            }
        }
    }

    private fun observePendingSos() {
        viewModelScope.launch {
            alertRepository.observePendingSos().collect { pending ->
                _uiState.update {
                    it.copy(
                        hasPendingSos = pending,
                        queuedMessage = if (pending) {
                            OfflineSosQueuedException.MESSAGE
                        } else {
                            null
                        },
                    )
                }
            }
        }
    }

    private fun observeHeartbeatWarning() {
        viewModelScope.launch {
            alertSessionManager.heartbeatWarning.collect { warning ->
                _uiState.update { it.copy(heartbeatWarning = warning) }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        countdownJob?.cancel()
    }

    companion object {
        const val COUNTDOWN_SECONDS = 5
        const val WHATSAPP_DELIVERY_WARNING =
            "Alert created but notifications may have failed."
    }
}
