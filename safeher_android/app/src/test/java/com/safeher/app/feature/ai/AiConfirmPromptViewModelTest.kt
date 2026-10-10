package com.safeher.app.feature.ai

import app.cash.turbine.test
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.ai.PendingAudioDetection
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
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
class AiConfirmPromptViewModelTest {

    private val coordinator: AiMonitoringCoordinator = mockk(relaxed = true)
    private val events = MutableSharedFlow<AiCoordinatorEvent>(extraBufferCapacity = 8)
    private val detection: PendingAudioDetection = mockk(relaxed = true)

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { coordinator.events } returns events
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel(): AiConfirmPromptViewModel {
        return AiConfirmPromptViewModel(coordinator)
    }

    @Test
    fun showEmergencyConfirmation_opensHelpStep() = runTest {
        val viewModel = createViewModel()

        events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))

        val state = viewModel.uiState.value
        assertTrue(state.visible)
        assertEquals(AiConfirmPromptStep.HELP, state.step)
        assertEquals(30, state.secondsRemaining)
    }

    @Test
    fun imOkay_callsCoordinatorFalse_andHides() = runTest {
        val viewModel = createViewModel()
        events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))

        viewModel.onImOkay()

        verify { coordinator.onEmergencyConfirmation(false) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        assertFalse(viewModel.uiState.value.visible)
    }

    @Test
    fun needHelp_doesNotConfirmSos() = runTest {
        val viewModel = createViewModel()
        events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))

        viewModel.onNeedHelp()

        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(false) }
        assertEquals(AiConfirmPromptStep.SEND_ALERT, viewModel.uiState.value.step)
        assertTrue(viewModel.uiState.value.visible)
    }

    @Test
    fun cancelSendAlert_callsCoordinatorFalse() = runTest {
        val viewModel = createViewModel()
        events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))
        viewModel.onNeedHelp()

        viewModel.onCancelSendAlert()

        verify { coordinator.onEmergencyConfirmation(false) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        assertFalse(viewModel.uiState.value.visible)
    }

    @Test
    fun sendEmergencyAlert_callsCoordinatorTrue() = runTest {
        val viewModel = createViewModel()
        events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))
        viewModel.onNeedHelp()

        viewModel.onSendEmergencyAlert()

        verify { coordinator.onEmergencyConfirmation(true) }
        assertFalse(viewModel.uiState.value.visible)
    }

    @Test
    fun coordinatorNavigateToSosCountdown_emitsOverlayEvent() = runTest {
        val viewModel = createViewModel()

        viewModel.events.test {
            events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            assertEquals(AiConfirmPromptEvent.NavigateToSosCountdown, awaitItem())
        }
    }
}
