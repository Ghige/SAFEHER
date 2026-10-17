package com.safeher.app.feature.ai

import app.cash.turbine.test
import com.safeher.app.services.AiCoordinatorEvent
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.ai.AiConfirmFirstPolicy
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
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
    private val confirmSecondsRemaining = MutableStateFlow(0)
    private val confirmPromptKind = MutableStateFlow<AiConfirmFirstPolicy.PromptKind?>(null)

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { coordinator.events } returns events
        every { coordinator.confirmSecondsRemaining } returns confirmSecondsRemaining
        every { coordinator.confirmPromptKind } returns confirmPromptKind
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

        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
                recommendedAction = "confirm_30s",
                countdownSeconds = 30,
                reason = "test",
            ),
        )

        val state = viewModel.uiState.value
        assertTrue(state.visible)
        assertEquals(AiConfirmPromptStep.HELP, state.step)
        assertEquals("SUSPICIOUS", state.promptKind)
        assertEquals(30, state.secondsRemaining)
    }

    @Test
    fun imOkay_callsCoordinatorFalse_andHides() = runTest {
        val viewModel = createViewModel()
        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.EMERGENCY,
                recommendedAction = "fire_immediately",
                countdownSeconds = 30,
                reason = "test",
            ),
        )

        viewModel.onImOkay()

        verify { coordinator.onEmergencyConfirmation(false) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        assertFalse(viewModel.uiState.value.visible)
    }

    @Test
    fun needHelp_pausesTimeout_doesNotConfirmSos() = runTest {
        val viewModel = createViewModel()
        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
                recommendedAction = "confirm_30s",
                countdownSeconds = 20,
                reason = "test",
            ),
        )

        viewModel.onNeedHelp()

        verify { coordinator.pauseConfirmTimeoutForSecondStep() }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(false) }
        assertEquals(AiConfirmPromptStep.SEND_ALERT, viewModel.uiState.value.step)
        assertTrue(viewModel.uiState.value.visible)
    }

    @Test
    fun cancelSendAlert_callsCoordinatorFalse() = runTest {
        val viewModel = createViewModel()
        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
                recommendedAction = "confirm_30s",
                countdownSeconds = 30,
                reason = "test",
            ),
        )
        viewModel.onNeedHelp()

        viewModel.onCancelSendAlert()

        verify { coordinator.onEmergencyConfirmation(false) }
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
        assertFalse(viewModel.uiState.value.visible)
    }

    @Test
    fun sendEmergencyAlert_callsCoordinatorTrue() = runTest {
        val viewModel = createViewModel()
        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
                recommendedAction = "confirm_30s",
                countdownSeconds = 30,
                reason = "test",
            ),
        )
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

    @Test
    fun timeoutEnded_hidesPrompt() = runTest {
        val viewModel = createViewModel()
        events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = null,
                promptKind = AiConfirmFirstPolicy.PromptKind.SUSPICIOUS,
                recommendedAction = "confirm_30s",
                countdownSeconds = 30,
                reason = "test",
            ),
        )

        events.emit(
            AiCoordinatorEvent.ConfirmSessionEnded(
                outcome = "NO_RESPONSE_DISMISS_SAFE",
                userMessage = "No response",
            ),
        )

        assertFalse(viewModel.uiState.value.visible)
        verify(exactly = 0) { coordinator.onEmergencyConfirmation(true) }
    }
}
