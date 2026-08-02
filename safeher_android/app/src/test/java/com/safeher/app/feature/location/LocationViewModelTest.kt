package com.safeher.app.feature.location

import app.cash.turbine.test
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.GeoCoordinates
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.model.TrackLink
import com.safeher.app.domain.repository.LocationRepository
import com.safeher.app.services.LocationPermissionManager
import com.safeher.app.services.LocationPermissionStatus
import com.safeher.app.services.LocationProvider
import com.safeher.app.services.LocationTrackingService
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LocationViewModelTest {

    private val locationRepository: LocationRepository = mockk()
    private val locationProvider: LocationProvider = mockk(relaxed = true)
    private val permissionManager: LocationPermissionManager = mockk()
    private val locationTrackingService: LocationTrackingService = mockk(relaxed = true)
    private val alertSessionManager: AlertSessionManager = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private lateinit var viewModel: LocationViewModel

    private val activeAlertFlow = MutableStateFlow<SafetyAlert?>(null)
    private val isTrackingFlow = MutableStateFlow(false)
    private val testDispatcher = StandardTestDispatcher()

    private val sampleAlert = SafetyAlert(
        id = "alert-uuid-123",
        triggerType = "manual",
        latitude = 12.97,
        longitude = 77.59,
        status = "active",
        startedAt = "2026-08-02T10:00:00Z",
        endedAt = null,
        evidenceUrl = null,
    )

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        every { networkMonitor.isOnline } returns flowOf(true)
        every { alertSessionManager.activeAlert } returns activeAlertFlow
        every { locationTrackingService.isTracking } returns isTrackingFlow
        every { permissionManager.hasLocationPermission() } returns true
        every { permissionManager.isGpsEnabled() } returns true
        every { permissionManager.getPermissionStatus(any(), any()) } returns LocationPermissionStatus.GRANTED
        every { permissionManager.openAppSettings() } returns Unit
        every { permissionManager.openLocationSettings() } returns Unit
        coEvery { locationProvider.getCurrentLocation() } returns GeoCoordinates(12.97, 77.59)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel() {
        viewModel = LocationViewModel(
            locationRepository,
            locationProvider,
            permissionManager,
            locationTrackingService,
            alertSessionManager,
            networkMonitor,
        )
    }

    @Test
    fun loadCurrentLocation_success_updatesCoords() = runTest(testDispatcher) {
        createViewModel()
        viewModel.loadCurrentLocation()
        testScheduler.advanceUntilIdle()

        assertEquals(GeoCoordinates(12.97, 77.59), viewModel.uiState.value.currentLocation)
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun generateTrackLink_success_emitsOpenUrl() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        coEvery { locationRepository.getTrackLink("alert-uuid-123") } returns Result.success(
            TrackLink("https://safeher.app/track?token=abc", 24),
        )
        createViewModel()
        testScheduler.advanceUntilIdle()

        viewModel.events.test {
            viewModel.generateTrackLink()
            testScheduler.advanceUntilIdle()
            assertEquals(
                LocationEvent.OpenTrackUrl("https://safeher.app/track?token=abc"),
                awaitItem(),
            )
            cancelAndIgnoreRemainingEvents()
        }
        assertEquals("https://safeher.app/track?token=abc", viewModel.uiState.value.trackUrl)
    }

    @Test
    fun generateTrackLink_failure_setsError() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        coEvery { locationRepository.getTrackLink("alert-uuid-123") } returns Result.failure(
            Exception("No active alert found"),
        )
        createViewModel()
        testScheduler.advanceUntilIdle()

        viewModel.generateTrackLink()
        testScheduler.advanceUntilIdle()

        assertEquals("No active alert found", viewModel.uiState.value.error)
    }

    @Test
    fun observeActiveAlert_setsActiveAlertId() = runTest(testDispatcher) {
        createViewModel()
        activeAlertFlow.value = sampleAlert
        testScheduler.advanceUntilIdle()

        assertEquals("alert-uuid-123", viewModel.uiState.value.activeAlertId)
    }

    @Test
    fun onPermissionResult_denied_updatesStatus() = runTest(testDispatcher) {
        every { permissionManager.getPermissionStatus(false, true) } returns
            LocationPermissionStatus.PERMANENTLY_DENIED
        createViewModel()

        viewModel.onPermissionResult(granted = false, shouldShowRationale = false)
        testScheduler.advanceUntilIdle()

        assertEquals(LocationPermissionStatus.PERMANENTLY_DENIED, viewModel.uiState.value.permissionStatus)
    }

    @Test
    fun openAppSettings_delegatesToPermissionManager() = runTest(testDispatcher) {
        createViewModel()
        viewModel.openAppSettings()
        verify { permissionManager.openAppSettings() }
    }
}
