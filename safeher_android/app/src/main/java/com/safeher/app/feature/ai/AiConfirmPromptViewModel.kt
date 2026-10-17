package com.safeher.app.feature.ai

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
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

enum class AiConfirmPromptStep {
    HIDDEN,
    HELP,
    SEND_ALERT,
}

data class AiConfirmPromptUiState(
    val visible: Boolean = false,
    val step: AiConfirmPromptStep = AiConfirmPromptStep.HIDDEN,
    val promptKind: String? = null,
    val secondsRemaining: Int = 0,
)

sealed interface AiConfirmPromptEvent {
    data object NavigateToSosCountdown : AiConfirmPromptEvent
}

@HiltViewModel
class AiConfirmPromptViewModel @Inject constructor(
    private val coordinator: AiMonitoringCoordinator,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AiConfirmPromptUiState())
    val uiState: StateFlow<AiConfirmPromptUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<AiConfirmPromptEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<AiConfirmPromptEvent> = _events.asSharedFlow()

    init {
        observeCoordinator()
    }

    fun onImOkay() {
        if (!isOnStep(AiConfirmPromptStep.HELP)) return
        hidePrompt()
        coordinator.onEmergencyConfirmation(false)
    }

    fun onNeedHelp() {
        if (!isOnStep(AiConfirmPromptStep.HELP)) return
        coordinator.pauseConfirmTimeoutForSecondStep()
        _uiState.update {
            it.copy(visible = true, step = AiConfirmPromptStep.SEND_ALERT)
        }
    }

    fun onCancelSendAlert() {
        if (!isOnStep(AiConfirmPromptStep.SEND_ALERT)) return
        hidePrompt()
        coordinator.onEmergencyConfirmation(false)
    }

    fun onSendEmergencyAlert() {
        if (!isOnStep(AiConfirmPromptStep.SEND_ALERT)) return
        hidePrompt()
        coordinator.onEmergencyConfirmation(true)
    }

    private fun isOnStep(step: AiConfirmPromptStep): Boolean {
        val state = _uiState.value
        return state.visible && state.step == step
    }

    private fun hidePrompt() {
        _uiState.update {
            it.copy(
                visible = false,
                step = AiConfirmPromptStep.HIDDEN,
                secondsRemaining = 0,
            )
        }
    }

    private fun observeCoordinator() {
        viewModelScope.launch {
            coordinator.confirmPromptKind.collect { kind ->
                if (kind == null) {
                    hidePrompt()
                    _uiState.update { it.copy(promptKind = null) }
                } else {
                    _uiState.update { current ->
                        if (current.step == AiConfirmPromptStep.SEND_ALERT) {
                            current.copy(visible = true, promptKind = kind.name)
                        } else {
                            current.copy(
                                visible = true,
                                step = AiConfirmPromptStep.HELP,
                                promptKind = kind.name,
                            )
                        }
                    }
                }
            }
        }
        viewModelScope.launch {
            coordinator.confirmSecondsRemaining.collect { seconds ->
                _uiState.update { it.copy(secondsRemaining = seconds) }
            }
        }
        viewModelScope.launch {
            coordinator.events.collect { event ->
                when (event) {
                    is AiCoordinatorEvent.ShowEmergencyConfirmation -> {
                        _uiState.update {
                            it.copy(
                                visible = true,
                                step = AiConfirmPromptStep.HELP,
                                promptKind = event.promptKind.name,
                                secondsRemaining = event.countdownSeconds,
                            )
                        }
                    }
                    is AiCoordinatorEvent.ConfirmSessionTick -> {
                        _uiState.update { it.copy(secondsRemaining = event.secondsRemaining) }
                    }
                    is AiCoordinatorEvent.ConfirmSessionEnded -> hidePrompt()
                    AiCoordinatorEvent.NavigateToSosCountdown -> {
                        hidePrompt()
                        _events.emit(AiConfirmPromptEvent.NavigateToSosCountdown)
                    }
                    AiCoordinatorEvent.NavigateToActiveAlert -> Unit
                }
            }
        }
    }
}
