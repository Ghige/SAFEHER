package com.safeher.app.feature.sos

import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
class AlertHistoryViewModelTest {

    private val alertRepository: AlertRepository = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private lateinit var viewModel: AlertHistoryViewModel

    private val history = listOf(
        SafetyAlert(
            id = "alert-1",
            triggerType = "manual",
            latitude = null,
            longitude = null,
            status = "cancelled",
            startedAt = "2026-08-01T10:00:00Z",
            endedAt = "2026-08-01T10:10:00Z",
            evidenceUrl = null,
        ),
    )

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { networkMonitor.isOnline } returns flowOf(true)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun loadHistory_success_updatesList() = runTest {
        coEvery { alertRepository.getHistory() } returns Result.success(history)
        viewModel = AlertHistoryViewModel(alertRepository, networkMonitor)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(history, viewModel.uiState.value.history)
    }

    @Test
    fun loadHistory_failure_setsError() = runTest {
        coEvery { alertRepository.getHistory() } returns Result.failure(Exception("Offline"))
        viewModel = AlertHistoryViewModel(alertRepository, networkMonitor)

        assertEquals("Offline", viewModel.uiState.value.error)
        assertTrue(viewModel.uiState.value.history.isEmpty())
    }

    @Test
    fun loadHistory_offline_setsOfflineFlag() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)
        coEvery { alertRepository.getHistory() } returns Result.success(history)
        viewModel = AlertHistoryViewModel(alertRepository, networkMonitor)

        assertTrue(viewModel.uiState.value.isOffline)
    }
}
