package com.safeher.app.core.session

import com.safeher.app.services.LocationTrackingService
import com.safeher.app.services.AiMonitoringCoordinator
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SessionCleanupManager @Inject constructor(
    private val locationTrackingService: LocationTrackingService,
    private val aiMonitoringCoordinator: AiMonitoringCoordinator,
    private val alertSessionManager: AlertSessionManager,
    private val authSessionManager: AuthSessionManager,
) {

    suspend fun stopTrackingAndClearAlert() {
        locationTrackingService.stopTracking()
        aiMonitoringCoordinator.stopMonitoring()
        alertSessionManager.clearActiveAlert()
    }

    suspend fun performLogout() {
        stopTrackingAndClearAlert()
        authSessionManager.logout()
    }

    suspend fun performSessionExpired() {
        stopTrackingAndClearAlert()
        authSessionManager.onSessionExpired()
    }
}
