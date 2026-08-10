package com.safeher.app.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.domain.repository.ContactsRepository
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.LocationTrackingService
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
class DashboardViewModel @Inject constructor(
    private val userRepository: UserRepository,
    private val contactsRepository: ContactsRepository,
    private val settingsStore: SettingsStore,
    private val aiMonitoringCoordinator: AiMonitoringCoordinator,
    private val locationTrackingService: LocationTrackingService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DashboardEvent>()
    val events: SharedFlow<DashboardEvent> = _events.asSharedFlow()

    init {
        observeNetwork()
        observeHomeSignals()
        loadProfile()
        loadContacts()
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

    fun loadContacts() {
        viewModelScope.launch {
            contactsRepository.getContacts().onSuccess { contacts ->
                _uiState.update { it.copy(emergencyContacts = contacts) }
            }
        }
    }

    fun onQuickAction(feature: QuickActionFeature) {
        viewModelScope.launch {
            _events.emit(DashboardEvent.NavigateToComingSoon(feature.routeKey))
        }
    }

    fun onNavigate(feature: QuickActionFeature) {
        viewModelScope.launch {
            _events.emit(DashboardEvent.NavigateToComingSoon(feature.routeKey))
        }
    }

    private fun observeHomeSignals() {
        viewModelScope.launch {
            combine(
                settingsStore.aiAudioDetectionEnabled,
                aiMonitoringCoordinator.isMonitoring,
                aiMonitoringCoordinator.riskAssessment,
                locationTrackingService.isTracking,
            ) { enabled, monitoring, risk, tracking ->
                val status = when {
                    !enabled -> AiHomeStatus.OFF
                    risk != null -> AiHomeStatus.DETECTING
                    monitoring -> AiHomeStatus.LISTENING
                    else -> AiHomeStatus.NORMAL
                }
                HomeSignals(
                    enabled = enabled,
                    monitoring = monitoring,
                    status = status,
                    tracking = tracking,
                )
            }.collect { signals ->
                _uiState.update {
                    it.copy(
                        aiMonitoringEnabled = signals.enabled,
                        aiIsMonitoring = signals.monitoring,
                        aiStatus = signals.status,
                        isLocationSharingActive = signals.tracking,
                    )
                }
            }
        }
    }

    private data class HomeSignals(
        val enabled: Boolean,
        val monitoring: Boolean,
        val status: AiHomeStatus,
        val tracking: Boolean,
    )

    private fun observeNetwork() {
        viewModelScope.launch {
            userRepository.observeNetworkStatus().collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }
}
