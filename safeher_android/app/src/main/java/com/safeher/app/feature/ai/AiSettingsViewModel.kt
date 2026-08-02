package com.safeher.app.feature.ai

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.services.AiMonitoringCoordinator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AiSettingsUiState(
    val monitoringEnabled: Boolean = false,
    val isIsolated: Boolean = false,
    val modelsAvailable: Boolean = false,
)

@HiltViewModel
class AiSettingsViewModel @Inject constructor(
    private val coordinator: AiMonitoringCoordinator,
) : ViewModel() {

    val uiState: StateFlow<AiSettingsUiState> = combine(
        coordinator.isMonitoring,
        coordinator.isIsolated,
        coordinator.modelsAvailable,
    ) { monitoring, isolated, models ->
        AiSettingsUiState(
            monitoringEnabled = monitoring,
            isIsolated = isolated,
            modelsAvailable = models,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AiSettingsUiState())

    fun setMonitoringEnabled(enabled: Boolean) {
        viewModelScope.launch { coordinator.setMonitoringEnabled(enabled) }
    }

    fun setIsIsolated(isolated: Boolean) {
        viewModelScope.launch { coordinator.setIsIsolated(isolated) }
    }
}
