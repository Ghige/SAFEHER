package com.safeher.app.feature.sos

import app.cash.turbine.test
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.data.repository.OfflineSosQueuedException
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.feature.sos.util.SosLocationHelper
import com.safeher.app.feature.sos.util.SosPreflightChecker
import com.safeher.app.feature.sos.util.SosPreflightResult
import com.safeher.app.services.ApplicationCoroutineScope
import com.safeher.app.services.BatteryOptimizationManager
import com.safeher.app.services.LocationPermissionManager
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
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SOSViewModelTest {

    private val alertRepository: AlertRepository = mockk(relaxed = true)
    private val alertSessionManager: AlertSessionManager = mockk(relaxed = true)
    private val networkMonitor: NetworkMonitor = mockk()
    private val locationHelper: SosLocationHelper = mockk()
    private val preflightChecker: SosPreflightChecker = mockk()
    private val locationPermissionManager: LocationPermissionManager = mockk(relaxed = true)
    private val batteryOptimizationManager: BatteryOptimizationManager = mockk(relaxed = true)
    private val applicationScope: ApplicationCoroutineScope = mockk(relaxed = true)
    private lateinit var viewModel: SOSViewModel

    private val activeAlertFlow = MutableStateFlow<SafetyAlert?>(null)
    private val heartbeatWarningFlow = MutableStateFlow(false)
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
        every { alertSessionManager.heartbeatWarning } returns heartbeatWarningFlow
        coEvery { alertSessionManager.restoreActiveAlert() } returns Unit
        coEvery { alertSessionManager.awaitRestoreAttempt() } returns Unit
        coEvery { locationHelper.getCurrentCoordinates() } returns null
        every { preflightChecker.evaluate() } returns SosPreflightResult(
            items = emptyList(),
            locationAvailable = false,
        )
        every { alertRepository.observePendingSos() } returns flowOf(false)
        every { applicationScope.scope } returns kotlinx.coroutines.CoroutineScope(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel() {
        viewModel = SOSViewModel(
            alertRepository,
            alertSessionManager,
            networkMonitor,
            locationHelper,
            preflightChecker,
            locationPermissionManager,
            batteryOptimizationManager,
            applicationScope,
        )
    }

    @Test
    fun observeSession_whenAlertBecomesOngoing_emitsNavigateToActive() = runTest(testDispatcher) {
        createViewModel()
        testScheduler.runCurrent()

        viewModel.events.test {
            activeAlertFlow.value = sampleAlert
            testScheduler.advanceUntilIdle()
            assertEquals(SOSEvent.NavigateToActive, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun syncActiveAlertUi_withOngoingAlert_emitsNavigateToActive() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.events.test {
            viewModel.syncActiveAlertUi()
            testScheduler.advanceUntilIdle()
            assertEquals(SOSEvent.NavigateToActive, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
        coVerify(exactly = 0) { alertSessionManager.restoreActiveAlert() }
    }

    @Test
    fun onSosButtonClick_withActiveAlert_navigatesToActive() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.events.test {
            viewModel.onSosButtonClick()
            testScheduler.advanceUntilIdle()
            assertEquals(SOSEvent.NavigateToActive, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun onSosButtonClick_withoutActiveAlert_navigatesToCountdown() = runTest(testDispatcher) {
        createViewModel()

        viewModel.events.test {
            viewModel.onSosButtonClick()
            testScheduler.advanceUntilIdle()
            assertEquals(SOSEvent.NavigateToCountdown, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun cancelCountdown_clearsCountdownAndNavigatesBack() = runTest(testDispatcher) {
        createViewModel()
        viewModel.startCountdown()
        testScheduler.runCurrent()
        assertEquals(5, viewModel.uiState.value.countdownSeconds)

        viewModel.events.test {
            viewModel.cancelCountdown()
            testScheduler.advanceUntilIdle()
            assertNull(viewModel.uiState.value.countdownSeconds)
            assertEquals(SOSEvent.NavigateBack, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun triggerSos_success_storesAlertAndNavigatesToActive() = runTest(testDispatcher) {
        coEvery {
            alertRepository.triggerAlert(null, null)
        } returns Result.success(sampleAlert)

        createViewModel()

        viewModel.events.test {
            viewModel.triggerSos()
            testScheduler.advanceUntilIdle()
            assertFalse(viewModel.uiState.value.isTriggering)
            assertEquals(sampleAlert, viewModel.uiState.value.activeAlert)
            coVerify { alertSessionManager.setActiveAlert(sampleAlert) }
            verify { alertSessionManager.startHeartbeat("alert-uuid-123", any()) }
            assertEquals(SOSEvent.NavigateToActive, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun triggerSos_failure_setsErrorAndNavigatesBack() = runTest(testDispatcher) {
        coEvery {
            alertRepository.triggerAlert(null, null)
        } returns Result.failure(Exception("No emergency contacts configured"))

        createViewModel()

        viewModel.events.test {
            viewModel.triggerSos()
            testScheduler.advanceUntilIdle()
            assertEquals("No emergency contacts configured", viewModel.uiState.value.error)
            assertEquals(SOSEvent.NavigateBack, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun requestCancelActiveAlert_whenOffline_setsErrorWithoutDialog() = runTest(testDispatcher) {
        every { networkMonitor.isOnline } returns flowOf(false)
        createViewModel()
        testScheduler.advanceUntilIdle()

        viewModel.requestCancelActiveAlert()

        assertFalse(viewModel.uiState.value.showCancelDialog)
        assertEquals(SOSViewModel.OFFLINE_CANCEL_MESSAGE, viewModel.uiState.value.error)
        coVerify(exactly = 0) { alertRepository.cancelAlert(any()) }
    }

    @Test
    fun confirmCancelActiveAlert_success_clearsAlertAndNavigatesBack() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        coEvery { alertRepository.cancelAlert("alert-uuid-123") } returns Result.success(
            sampleAlert.copy(status = "cancelled", endedAt = "2026-08-02T10:05:00Z"),
        )

        createViewModel()

        viewModel.events.test {
            viewModel.confirmCancelActiveAlert()
            testScheduler.advanceUntilIdle()
            coVerify { alertSessionManager.clearActiveAlert() }
            assertNull(viewModel.uiState.value.activeAlert)
            assertEquals(SOSEvent.NavigateBack, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun confirmCancelActiveAlert_usesUiStateIdWhenSessionNull() = runTest(testDispatcher) {
        coEvery { alertRepository.triggerAlert(null, null) } returns Result.success(sampleAlert)
        coEvery { alertRepository.cancelAlert("alert-uuid-123") } returns Result.success(
            sampleAlert.copy(status = "cancelled", endedAt = "2026-08-02T10:05:00Z"),
        )
        createViewModel()
        viewModel.triggerSos()
        testScheduler.advanceUntilIdle()
        assertEquals(sampleAlert, viewModel.uiState.value.activeAlert)
        assertNull(activeAlertFlow.value)

        viewModel.events.test {
            viewModel.confirmCancelActiveAlert()
            testScheduler.advanceUntilIdle()
            coVerify { alertRepository.cancelAlert("alert-uuid-123") }
            coVerify { alertSessionManager.clearActiveAlert() }
            assertEquals(SOSEvent.NavigateBack, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun confirmCancelActiveAlert_withoutId_setsErrorAndDoesNotCallApi() = runTest(testDispatcher) {
        createViewModel()
        testScheduler.advanceUntilIdle()

        viewModel.confirmCancelActiveAlert()
        testScheduler.advanceUntilIdle()

        assertEquals(SOSViewModel.MISSING_ALERT_ID_MESSAGE, viewModel.uiState.value.error)
        coVerify(exactly = 0) { alertRepository.cancelAlert(any()) }
    }

    @Test
    fun confirmCancelActiveAlert_failure_setsError() = runTest(testDispatcher) {
        activeAlertFlow.value = sampleAlert
        coEvery { alertRepository.cancelAlert("alert-uuid-123") } returns Result.failure(
            Exception("Network error"),
        )

        createViewModel()
        viewModel.confirmCancelActiveAlert()
        testScheduler.advanceUntilIdle()

        assertEquals("Network error", viewModel.uiState.value.error)
    }

    @Test
    fun startCountdown_countsDownFromFive() = runTest(testDispatcher) {
        coEvery { alertRepository.triggerAlert(null, null) } returns Result.success(sampleAlert)
        createViewModel()

        viewModel.startCountdown()
        testScheduler.runCurrent()
        assertEquals(5, viewModel.uiState.value.countdownSeconds)

        advanceTimeBy(5_000)
        testScheduler.advanceUntilIdle()
        coVerify { alertRepository.triggerAlert(null, null) }
    }
}
