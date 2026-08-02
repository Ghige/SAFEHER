package com.safeher.app.feature.ai

import app.cash.turbine.test
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.domain.model.AiAction
import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.AudioPermissionManager
import com.safeher.app.services.AudioPermissionStatus
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
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
class AiMonitoringViewModelTest {

    private val coordinator: AiMonitoringCoordinator = mockk(relaxed = true)
    private val audioPermissionManager: AudioPermissionManager = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val context: android.content.Context = mockk(relaxed = true)
    private lateinit var viewModel: AiMonitoringViewModel

    private val isMonitoring = MutableStateFlow(false)
    private val modelsAvailable = MutableStateFlow(false)
    private val confidence = MutableStateFlow<AiConfidenceResult?>(null)
    private val isLoadingConfidence = MutableStateFlow(false)
    private val error = MutableStateFlow<String?>(null)
    private val audioLevel = MutableStateFlow(0f)
    private val movementLevel = MutableStateFlow(0f)
    private val isIsolated = MutableStateFlow(false)
    private val isAppInForeground = MutableStateFlow(true)
    private val events = MutableSharedFlow<AiCoordinatorEvent>()

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { networkMonitor.isOnline } returns flowOf(true)
        every { coordinator.isMonitoring } returns isMonitoring
        every { coordinator.modelsAvailable } returns modelsAvailable
        every { coordinator.confidence } returns confidence
        every { coordinator.isLoadingConfidence } returns isLoadingConfidence
        every { coordinator.error } returns error
        every { coordinator.audioLevel } returns audioLevel
        every { coordinator.movementLevel } returns movementLevel
        every { coordinator.isIsolated } returns isIsolated
        every { coordinator.isAppInForeground } returns isAppInForeground
        every { coordinator.events } returns events
        every { audioPermissionManager.hasRecordAudioPermission() } returns true
        every { audioPermissionManager.getPermissionStatus(any()) } returns AudioPermissionStatus.GRANTED
        coEvery { coordinator.setMonitoringEnabled(any()) } returns Unit
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel() {
        viewModel = AiMonitoringViewModel(
            coordinator,
            audioPermissionManager,
            networkMonitor,
            context,
        )
    }

    @Test
    fun onToggleMonitoring_enabled_startsMonitoring() = runTest {
        createViewModel()

        viewModel.onToggleMonitoring(true)

        coVerify { coordinator.setMonitoringEnabled(true) }
    }

    @Test
    fun onToggleMonitoring_withoutPermission_emitsRequestPermission() = runTest {
        every { audioPermissionManager.hasRecordAudioPermission() } returns false
        every { audioPermissionManager.getPermissionStatus(any()) } returns AudioPermissionStatus.DENIED
        createViewModel()

        viewModel.events.test {
            viewModel.onToggleMonitoring(true)
            assertEquals(AiMonitoringEvent.RequestAudioPermission, awaitItem())
        }
        coVerify(exactly = 0) { coordinator.setMonitoringEnabled(true) }
    }

    @Test
    fun observeCoordinator_updatesModelsAvailable() = runTest {
        modelsAvailable.value = false
        createViewModel()

        assertFalse(viewModel.uiState.value.modelsAvailable)

        modelsAvailable.value = true
        assertTrue(viewModel.uiState.value.modelsAvailable)
    }

    @Test
    fun observeCoordinator_updatesConfidence() = runTest {
        createViewModel()
        val result = AiConfidenceResult(
            totalScore = 70.0,
            action = AiAction.CONFIRM_30S,
            activateGpsStream = false,
            audioScore = 80.0,
            movementScore = 70.0,
            heartRateSpike = false,
            isNight = true,
            isIsolated = false,
        )
        confidence.value = result

        assertEquals(result, viewModel.uiState.value.confidence)
    }

    @Test
    fun coordinatorNavigateToSosCountdown_emitsEvent() = runTest {
        createViewModel()

        viewModel.events.test {
            events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            assertEquals(AiMonitoringEvent.NavigateToSosCountdown, awaitItem())
        }
    }

    @Test
    fun setAppInForeground_delegatesToCoordinator() = runTest {
        createViewModel()

        viewModel.setAppInForeground(false)

        coVerify { coordinator.setAppInForeground(false) }
    }
}
