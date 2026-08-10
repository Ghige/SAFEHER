package com.safeher.app.feature.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.domain.repository.SettingsRepository
import com.safeher.app.domain.repository.UserRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val userRepository: UserRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<SettingsEvent>()
    val events: SharedFlow<SettingsEvent> = _events.asSharedFlow()

    init {
        observePreferences()
        observeNetwork()
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val profileResult = settingsRepository.getProfile()
            val securityInfo = settingsRepository.getSecurityInfo()
            val permissions = settingsRepository.getPermissionStatuses()
            val batteryOk = settingsRepository.isBatteryOptimizationDisabled()
            profileResult.fold(
                onSuccess = { profile ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            profile = profile,
                            securityInfo = securityInfo,
                            permissionStatuses = permissions,
                            isBatteryOptimizationDisabled = batteryOk,
                        )
                    }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            securityInfo = securityInfo,
                            permissionStatuses = permissions,
                            isBatteryOptimizationDisabled = batteryOk,
                            error = error.message,
                        )
                    }
                },
            )
        }
    }

    fun refreshPermissions() {
        _uiState.update {
            it.copy(
                permissionStatuses = settingsRepository.getPermissionStatuses(),
                isBatteryOptimizationDisabled = settingsRepository.isBatteryOptimizationDisabled(),
            )
        }
    }

    fun setNotificationsEnabled(enabled: Boolean) = updatePref { settingsRepository.setNotificationsEnabled(enabled) }
    fun setSosNotificationsEnabled(enabled: Boolean) = updatePref { settingsRepository.setSosNotificationsEnabled(enabled) }
    fun setHelperNotificationsEnabled(enabled: Boolean) = updatePref { settingsRepository.setHelperNotificationsEnabled(enabled) }
    fun setAiNotificationsEnabled(enabled: Boolean) = updatePref { settingsRepository.setAiNotificationsEnabled(enabled) }
    fun setAiMonitoringEnabled(enabled: Boolean) = updatePref { settingsRepository.setAiMonitoringEnabled(enabled) }
    fun setAiAudioDetectionEnabled(enabled: Boolean) = updatePref { settingsRepository.setAiAudioDetectionEnabled(enabled) }
    fun setAiMovementDetectionEnabled(enabled: Boolean) = updatePref { settingsRepository.setAiMovementDetectionEnabled(enabled) }
    fun setAiSensitivity(sensitivity: AiSensitivity) = updatePref { settingsRepository.setAiSensitivity(sensitivity) }
    fun setAiHelpImproveEnabled(enabled: Boolean) = updatePref { settingsRepository.setAiHelpImproveEnabled(enabled) }
    fun setThemeMode(mode: AppThemeMode) = updatePref { settingsRepository.setThemeMode(mode) }
    fun setLanguage(language: String) = updatePref { settingsRepository.setLanguage(language) }

    fun openAppSettings() = settingsRepository.openAppSettings()
    fun openBatterySettings() = settingsRepository.openBatteryOptimizationSettings()

    fun logout() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoggingOut = true) }
            settingsRepository.logout()
            _uiState.update { it.copy(isLoggingOut = false) }
            _events.emit(SettingsEvent.NavigateToLogin)
        }
    }

    fun navigateTo(event: SettingsEvent) {
        viewModelScope.launch { _events.emit(event) }
    }

    private fun updatePref(block: suspend () -> Unit) {
        viewModelScope.launch { block() }
    }

    private fun observePreferences() {
        viewModelScope.launch {
            combine(
                settingsRepository.observeNotificationsEnabled(),
                settingsRepository.observeSosNotificationsEnabled(),
                settingsRepository.observeHelperNotificationsEnabled(),
                settingsRepository.observeAiNotificationsEnabled(),
                settingsRepository.observeAiMonitoringEnabled(),
            ) { notifications, sos, helper, aiNotif, aiMonitoring ->
                PreferencesPartial(notifications, sos, helper, aiNotif, aiMonitoring)
            }.collect { partial ->
                _uiState.update {
                    it.copy(
                        notificationsEnabled = partial.notifications,
                        sosNotificationsEnabled = partial.sos,
                        helperNotificationsEnabled = partial.helper,
                        aiNotificationsEnabled = partial.aiNotif,
                        aiMonitoringEnabled = partial.aiMonitoring,
                    )
                }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeAiAudioDetectionEnabled().collect { enabled ->
                _uiState.update { it.copy(aiAudioDetectionEnabled = enabled) }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeAiMovementDetectionEnabled().collect { enabled ->
                _uiState.update { it.copy(aiMovementDetectionEnabled = enabled) }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeAiSensitivity().collect { sensitivity ->
                _uiState.update { it.copy(aiSensitivity = sensitivity) }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeAiHelpImproveEnabled().collect { enabled ->
                _uiState.update { it.copy(aiHelpImproveEnabled = enabled) }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeThemeMode().collect { theme ->
                _uiState.update { it.copy(themeMode = theme) }
            }
        }
        viewModelScope.launch {
            settingsRepository.observeLanguage().collect { language ->
                _uiState.update { it.copy(language = language) }
            }
        }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            userRepository.observeNetworkStatus().collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }

    private data class PreferencesPartial(
        val notifications: Boolean,
        val sos: Boolean,
        val helper: Boolean,
        val aiNotif: Boolean,
        val aiMonitoring: Boolean,
    )
}
