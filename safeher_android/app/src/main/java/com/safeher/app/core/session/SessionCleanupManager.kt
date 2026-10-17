package com.safeher.app.core.session

import com.safeher.app.core.datastore.PendingSosStore
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.LocationTrackingService
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SessionCleanupManager @Inject constructor(
    private val locationTrackingService: LocationTrackingService,
    private val aiMonitoringCoordinator: AiMonitoringCoordinator,
    private val alertSessionManager: AlertSessionManager,
    private val authSessionManager: AuthSessionManager,
    private val userRepository: UserRepository,
    private val pendingSosStore: PendingSosStore,
) {

    suspend fun stopTrackingAndClearAlert() {
        locationTrackingService.stopTracking()
        aiMonitoringCoordinator.stopMonitoring()
        alertSessionManager.clearActiveAlert()
        pendingSosStore.clear()
    }

    suspend fun performLogout() {
        stopTrackingAndClearAlert()
        userRepository.clearProfileCache()
        authSessionManager.logout()
    }

    suspend fun performSessionExpired() {
        stopTrackingAndClearAlert()
        userRepository.clearProfileCache()
        authSessionManager.onSessionExpired()
    }
}
