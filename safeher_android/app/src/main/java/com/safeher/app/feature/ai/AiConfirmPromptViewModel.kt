package com.safeher.app.feature.ai

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
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

enum class AiConfirmPromptStep {
    HIDDEN,
    HELP,
    SEND_ALERT,
}

data class AiConfirmPromptUiState(
    val visible: Boolean = false,
    val step: AiConfirmPromptStep = AiConfirmPromptStep.HIDDEN,
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

    private var timeoutJob: Job? = null

    init {
        observeCoordinator()
    }

    fun onImOkay() {
        if (!isOnStep(AiConfirmPromptStep.HELP)) return
        cancelTimeout()
        hidePrompt()
        coordinator.onEmergencyConfirmation(false)
    }

    fun onNeedHelp() {
        if (!isOnStep(AiConfirmPromptStep.HELP)) return
        cancelTimeout()
        _uiState.update {
            it.copy(visible = true, step = AiConfirmPromptStep.SEND_ALERT, secondsRemaining = 0)
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
        cancelTimeout()
        _uiState.update {
            it.copy(visible = false, step = AiConfirmPromptStep.HIDDEN, secondsRemaining = 0)
        }
    }

    private fun cancelTimeout() {
        timeoutJob?.cancel()
        timeoutJob = null
    }

    private fun startHelpTimeout() {
        cancelTimeout()
        timeoutJob = viewModelScope.launch {
            for (remaining in HELP_TIMEOUT_SECONDS downTo 1) {
                _uiState.update { it.copy(secondsRemaining = remaining) }
                delay(1_000)
            }
            if (isOnStep(AiConfirmPromptStep.HELP)) {
                hidePrompt()
                coordinator.onEmergencyConfirmation(false)
            }
        }
    }

    private fun observeCoordinator() {
        viewModelScope.launch {
            coordinator.events.collect { event ->
                when (event) {
                    is AiCoordinatorEvent.ShowEmergencyConfirmation -> {
                        _uiState.update {
                            it.copy(
                                visible = true,
                                step = AiConfirmPromptStep.HELP,
                                secondsRemaining = HELP_TIMEOUT_SECONDS,
                            )
                        }
                        startHelpTimeout()
                    }
                    AiCoordinatorEvent.NavigateToSosCountdown -> {
                        hidePrompt()
                        _events.emit(AiConfirmPromptEvent.NavigateToSosCountdown)
                    }
                    AiCoordinatorEvent.NavigateToActiveAlert -> Unit
                }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        cancelTimeout()
    }

    companion object {
        const val HELP_TIMEOUT_SECONDS = 30
    }
}
