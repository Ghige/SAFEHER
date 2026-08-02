package com.safeher.app.feature.location

import com.safeher.app.domain.model.GeoCoordinates
import com.safeher.app.services.LocationPermissionStatus

data class LocationUiState(
    val isLoading: Boolean = true,
    val currentLocation: GeoCoordinates? = null,
    val activeAlertId: String? = null,
    val isTracking: Boolean = false,
    val trackUrl: String? = null,
    val permissionStatus: LocationPermissionStatus = LocationPermissionStatus.DENIED,
    val isGpsEnabled: Boolean = true,
    val error: String? = null,
    val isOffline: Boolean = false,
    val followUser: Boolean = true,
)
