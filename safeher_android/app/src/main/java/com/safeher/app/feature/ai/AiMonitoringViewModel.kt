package com.safeher.app.feature.ai

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.AudioPermissionManager
import com.safeher.app.services.AudioPermissionStatus
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
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
class AiMonitoringViewModel @Inject constructor(
    private val coordinator: AiMonitoringCoordinator,
    private val audioPermissionManager: AudioPermissionManager,
    private val networkMonitor: NetworkMonitor,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AiMonitoringUiState())
    val uiState: StateFlow<AiMonitoringUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<AiMonitoringEvent>()
    val events: SharedFlow<AiMonitoringEvent> = _events.asSharedFlow()

    init {
        observeCoordinator()
        observeNetwork()
        updatePermissionStatus(shouldShowRationale = true)
    }

    fun onToggleMonitoring(enabled: Boolean) {
        if (enabled && !audioPermissionManager.hasRecordAudioPermission()) {
            viewModelScope.launch { _events.emit(AiMonitoringEvent.RequestAudioPermission) }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            coordinator.setMonitoringEnabled(enabled)
            _uiState.update { it.copy(isLoading = false) }
        }
    }

    fun onPermissionResult(granted: Boolean, shouldShowRationale: Boolean) {
        updatePermissionStatus(shouldShowRationale)
        if (granted) {
            viewModelScope.launch {
                coordinator.setMonitoringEnabled(true)
            }
        }
    }

    fun onOpenAppSettings() {
        context.startActivity(audioPermissionManager.createAppSettingsIntent())
    }

    fun setAppInForeground(inForeground: Boolean) {
        coordinator.setAppInForeground(inForeground)
    }

    fun refreshConfidence() {
        coordinator.refreshConfidence()
    }

    fun retry() {
        coordinator.clearError()
        coordinator.refreshConfidence()
    }

    fun clearError() {
        coordinator.clearError()
        _uiState.update { it.copy(error = null) }
    }

    fun clearSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    fun navigateToStatus() {
        viewModelScope.launch { _events.emit(AiMonitoringEvent.NavigateToStatus) }
    }

    fun navigateToSettings() {
        viewModelScope.launch { _events.emit(AiMonitoringEvent.NavigateToSettings) }
    }

    private fun observeCoordinator() {
        viewModelScope.launch {
            coordinator.isMonitoring.collect { monitoring ->
                _uiState.update {
                    it.copy(isMonitoring = monitoring, monitoringEnabled = monitoring)
                }
            }
        }
        viewModelScope.launch {
            coordinator.modelsAvailable.collect { available ->
                _uiState.update { it.copy(modelsAvailable = available) }
            }
        }
        viewModelScope.launch {
            coordinator.confidence.collect { confidence ->
                _uiState.update { it.copy(confidence = confidence) }
            }
        }
        viewModelScope.launch {
            coordinator.isLoadingConfidence.collect { loading ->
                _uiState.update { it.copy(isLoadingConfidence = loading) }
            }
        }
        viewModelScope.launch {
            coordinator.error.collect { error ->
                _uiState.update { it.copy(error = error) }
            }
        }
        viewModelScope.launch {
            coordinator.audioLevel.collect { level ->
                _uiState.update { it.copy(audioLevel = level) }
            }
        }
        viewModelScope.launch {
            coordinator.movementLevel.collect { level ->
                _uiState.update { it.copy(movementLevel = level) }
            }
        }
        viewModelScope.launch {
            coordinator.isIsolated.collect { isolated ->
                _uiState.update { it.copy(isIsolated = isolated) }
            }
        }
        viewModelScope.launch {
            coordinator.isAppInForeground.collect { foreground ->
                _uiState.update { it.copy(isAppInForeground = foreground) }
            }
        }
        viewModelScope.launch {
            coordinator.riskAssessment.collect { assessment ->
                _uiState.update {
                    it.copy(
                        riskLevelLabel = assessment?.riskLevel?.name,
                        rollingConfidence = assessment?.rollingAverage,
                        riskAssessment = assessment,
                    )
                }
            }
        }
        viewModelScope.launch {
            coordinator.modelStatus.collect { status ->
                _uiState.update {
                    it.copy(
                        modelStatusSummary =
                            "audio=${status.audioAvailable} speech=${status.speechMode} " +
                                "movement=${status.movementAvailable} contract=${status.contractVersion}",
                    )
                }
            }
        }
        viewModelScope.launch {
            coordinator.inferenceSnapshot.collect { snap ->
                _uiState.update {
                    it.copy(
                        localSdeState = snap?.localState,
                        localSdeAction = snap?.localAction,
                        audioLatencyMs = snap?.audioLatencyMs,
                        detectedPhrase = snap?.detectedPhrase,
                    )
                }
            }
        }
        viewModelScope.launch {
            coordinator.confirmSecondsRemaining.collect { seconds ->
                _uiState.update { it.copy(confirmSecondsRemaining = seconds) }
            }
        }
        viewModelScope.launch {
            coordinator.confirmPromptKind.collect { kind ->
                _uiState.update { it.copy(confirmPromptKind = kind?.name) }
            }
        }
        viewModelScope.launch {
            coordinator.events.collect { event ->
                when (event) {
                    AiCoordinatorEvent.NavigateToSosCountdown ->
                        _events.emit(AiMonitoringEvent.NavigateToSosCountdown)
                    AiCoordinatorEvent.NavigateToActiveAlert ->
                        _events.emit(AiMonitoringEvent.NavigateToActiveAlert)
                    is AiCoordinatorEvent.ShowEmergencyConfirmation -> {
                        _uiState.update {
                            it.copy(
                                pendingEmergencyConfirmation = true,
                                confirmPromptKind = event.promptKind.name,
                                confirmSecondsRemaining = event.countdownSeconds,
                                snackbarMessage = null,
                            )
                        }
                    }
                    is AiCoordinatorEvent.ConfirmSessionTick -> {
                        _uiState.update { it.copy(confirmSecondsRemaining = event.secondsRemaining) }
                    }
                    is AiCoordinatorEvent.ConfirmSessionEnded -> {
                        _uiState.update {
                            it.copy(
                                pendingEmergencyConfirmation = false,
                                confirmPromptKind = null,
                                confirmSecondsRemaining = 0,
                                snackbarMessage = event.userMessage,
                            )
                        }
                    }
                }
            }
        }
    }

    fun onEmergencyConfirmation(confirmedEmergency: Boolean) {
        _uiState.update { it.copy(pendingEmergencyConfirmation = false) }
        coordinator.onEmergencyConfirmation(confirmedEmergency)
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }

    private fun updatePermissionStatus(shouldShowRationale: Boolean) {
        val status = if (audioPermissionManager.hasRecordAudioPermission()) {
            AudioPermissionStatus.GRANTED
        } else {
            audioPermissionManager.getPermissionStatus(shouldShowRationale)
        }
        _uiState.update { it.copy(audioPermissionStatus = status) }
    }
}
