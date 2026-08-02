package com.safeher.app.feature.location

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.repository.LocationRepository
import com.safeher.app.services.LocationPermissionManager
import com.safeher.app.services.LocationProvider
import com.safeher.app.services.LocationTrackingService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
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
class LocationViewModel @Inject constructor(
    private val locationRepository: LocationRepository,
    private val locationProvider: LocationProvider,
    private val permissionManager: LocationPermissionManager,
    private val locationTrackingService: LocationTrackingService,
    private val alertSessionManager: AlertSessionManager,
    private val networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LocationUiState())
    val uiState: StateFlow<LocationUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<LocationEvent>()
    val events: SharedFlow<LocationEvent> = _events.asSharedFlow()

    private var locationJob: Job? = null

    init {
        observeNetwork()
        observeTracking()
        observeActiveAlert()
        refreshPermissionState()
        loadCurrentLocation()
    }

    fun refreshPermissionState(shouldShowRationale: Boolean = false, permissionDenied: Boolean = false) {
        val status = permissionManager.getPermissionStatus(shouldShowRationale, permissionDenied)
        _uiState.update {
            it.copy(
                permissionStatus = status,
                isGpsEnabled = permissionManager.isGpsEnabled(),
            )
        }
    }

    fun onPermissionResult(granted: Boolean, shouldShowRationale: Boolean) {
        if (granted) {
            refreshPermissionState()
            loadCurrentLocation()
            startLocationUpdates()
        } else {
            refreshPermissionState(
                shouldShowRationale = shouldShowRationale,
                permissionDenied = true,
            )
        }
    }

    fun loadCurrentLocation() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            if (!permissionManager.hasLocationPermission()) {
                _uiState.update { it.copy(isLoading = false) }
                return@launch
            }
            if (!permissionManager.isGpsEnabled()) {
                _uiState.update {
                    it.copy(isLoading = false, error = "Location services are disabled")
                }
                return@launch
            }
            val coords = locationProvider.getCurrentLocation()
            _uiState.update { it.copy(isLoading = false, currentLocation = coords) }
        }
    }

    fun startLocationUpdates() {
        if (!permissionManager.hasLocationPermission()) return
        locationJob?.cancel()
        locationJob = viewModelScope.launch {
            locationProvider.locationUpdates().collect { coords ->
                _uiState.update { it.copy(currentLocation = coords, isLoading = false) }
            }
        }
    }

    fun stopLocationUpdates() {
        locationJob?.cancel()
        locationJob = null
        locationProvider.stopLocationUpdates()
    }

    fun generateTrackLink() {
        val alertId = _uiState.value.activeAlertId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = locationRepository.getTrackLink(alertId)
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = { trackLink ->
                    _uiState.update { it.copy(trackUrl = trackLink.trackUrl) }
                    _events.emit(LocationEvent.OpenTrackUrl(trackLink.trackUrl))
                },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }

    fun navigateToTrack() {
        viewModelScope.launch { _events.emit(LocationEvent.NavigateToTrack) }
    }

    fun navigateToPermission() {
        viewModelScope.launch { _events.emit(LocationEvent.NavigateToPermission) }
    }

    fun openAppSettings() {
        permissionManager.openAppSettings()
    }

    fun openLocationSettings() {
        permissionManager.openLocationSettings()
    }

    fun toggleFollowUser() {
        _uiState.update { it.copy(followUser = !it.followUser) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }

    private fun observeTracking() {
        viewModelScope.launch {
            locationTrackingService.isTracking.collect { tracking ->
                _uiState.update { it.copy(isTracking = tracking) }
            }
        }
    }

    private fun observeActiveAlert() {
        viewModelScope.launch {
            alertSessionManager.activeAlert.collect { alert ->
                _uiState.update { it.copy(activeAlertId = alert?.takeIf { it.isOngoing }?.id) }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        stopLocationUpdates()
    }
}
