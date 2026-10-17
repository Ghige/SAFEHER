package com.safeher.app.core.session

import com.safeher.app.core.datastore.PendingSosStore
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.LocationTrackingService
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.coVerifyOrder
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Before
import org.junit.Test

class SessionCleanupManagerTest {

    private val locationTrackingService: LocationTrackingService = mockk(relaxed = true)
    private val aiMonitoringCoordinator: AiMonitoringCoordinator = mockk(relaxed = true)
    private val alertSessionManager: AlertSessionManager = mockk(relaxed = true)
    private val authSessionManager: AuthSessionManager = mockk(relaxed = true)
    private val userRepository: com.safeher.app.domain.repository.UserRepository = mockk(relaxed = true)
    private val pendingSosStore: PendingSosStore = mockk(relaxed = true)
    private lateinit var manager: SessionCleanupManager

    @Before
    fun setup() {
        coEvery { alertSessionManager.clearActiveAlert() } returns Unit
        coEvery { authSessionManager.logout() } returns Unit
        coEvery { authSessionManager.onSessionExpired() } returns Unit
        coEvery { pendingSosStore.clear() } returns Unit
        manager = SessionCleanupManager(
            locationTrackingService,
            aiMonitoringCoordinator,
            alertSessionManager,
            authSessionManager,
            userRepository,
            pendingSosStore,
        )
    }

    @Test
    fun performLogout_stopsTrackingClearsAlertPendingSosThenClearsJwt() = runTest {
        manager.performLogout()

        coVerifyOrder {
            locationTrackingService.stopTracking()
            aiMonitoringCoordinator.stopMonitoring()
            alertSessionManager.clearActiveAlert()
            pendingSosStore.clear()
            userRepository.clearProfileCache()
            authSessionManager.logout()
        }
    }

    @Test
    fun performSessionExpired_clearsPendingSos() = runTest {
        manager.performSessionExpired()

        coVerify { pendingSosStore.clear() }
        coVerifyOrder {
            locationTrackingService.stopTracking()
            aiMonitoringCoordinator.stopMonitoring()
            alertSessionManager.clearActiveAlert()
            pendingSosStore.clear()
            userRepository.clearProfileCache()
            authSessionManager.onSessionExpired()
        }
    }
}
