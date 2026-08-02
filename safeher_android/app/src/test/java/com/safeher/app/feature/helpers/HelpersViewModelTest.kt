package com.safeher.app.feature.helpers

import app.cash.turbine.test
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.NearbyHelper
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.HelpersRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
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
class HelpersViewModelTest {

    private val helpersRepository: HelpersRepository = mockk()
    private val alertSessionManager: AlertSessionManager = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private lateinit var viewModel: HelpersViewModel

    private val activeAlertFlow = MutableStateFlow<SafetyAlert?>(null)

    private val alertId = "550e8400-e29b-41d4-a716-446655440000"
    private val helperId = "660e8400-e29b-41d4-a716-446655440001"

    private val sampleAlert = SafetyAlert(
        id = alertId,
        triggerType = "manual",
        latitude = 12.97,
        longitude = 77.59,
        status = "active",
        startedAt = "2026-08-02T10:00:00Z",
        endedAt = null,
        evidenceUrl = null,
    )

    private val sampleHelper = NearbyHelper(
        id = helperId,
        alertId = alertId,
        status = "notified",
        notifiedAt = "2026-08-02T10:00:00Z",
        identityRevealed = true,
        approvedByUser = false,
        name = "Alex",
        phoneNumber = "9876543210",
    )

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { networkMonitor.isOnline } returns flowOf(true)
        every { alertSessionManager.activeAlert } returns activeAlertFlow
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel() {
        viewModel = HelpersViewModel(helpersRepository, alertSessionManager, networkMonitor)
    }

    @Test
    fun loadHelpers_withActiveAlert_updatesList() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        activeAlertFlow.value = sampleAlert
        createViewModel()

        assertEquals(alertId, viewModel.uiState.value.activeAlertId)
        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(listOf(sampleHelper), viewModel.uiState.value.helpers)
    }

    @Test
    fun loadHelpers_noActiveAlert_clearsList() = runTest {
        createViewModel()

        assertNull(viewModel.uiState.value.activeAlertId)
        assertTrue(viewModel.uiState.value.helpers.isEmpty())
    }

    @Test
    fun loadHelpers_failure_setsError() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.failure(Exception("Network error"))
        activeAlertFlow.value = sampleAlert
        createViewModel()

        assertEquals("Network error", viewModel.uiState.value.error)
    }

    @Test
    fun confirmRespond_accept_updatesHelper() = runTest {
        val updated = sampleHelper.copy(status = "responding", approvedByUser = true)
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        coEvery { helpersRepository.respondToAlert(alertId) } returns Result.success(updated)
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.onRespondClick(sampleHelper)
        viewModel.confirmRespond(HelperResponseAction.ACCEPT)

        assertNull(viewModel.uiState.value.helperToRespond)
        assertEquals("responding", viewModel.uiState.value.helpers.first().status)
        coVerify { helpersRepository.respondToAlert(alertId) }
    }

    @Test
    fun confirmRespond_decline_blocksHelper() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        coEvery { helpersRepository.blockHelper(helperId) } returns Result.success(Unit)
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.onRespondClick(sampleHelper)
        viewModel.confirmRespond(HelperResponseAction.DECLINE)

        assertTrue(viewModel.uiState.value.helpers.isEmpty())
        assertEquals(1, viewModel.uiState.value.blockedHelpers.size)
        coVerify { helpersRepository.blockHelper(helperId) }
    }

    @Test
    fun confirmBlock_movesHelperToBlockedList() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        coEvery { helpersRepository.blockHelper(helperId) } returns Result.success(Unit)
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.onBlockClick(sampleHelper)
        viewModel.confirmBlock()

        assertNull(viewModel.uiState.value.helperToBlock)
        assertTrue(viewModel.uiState.value.helpers.isEmpty())
        assertEquals(1, viewModel.uiState.value.blockedHelpers.size)
    }

    @Test
    fun onHelperClick_emitsNavigateToProfile() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.events.test {
            viewModel.onHelperClick(sampleHelper)
            assertEquals(HelpersEvent.NavigateToProfile(helperId), awaitItem())
        }
    }

    @Test
    fun refreshHelpers_reloadsFromRepository() = runTest {
        coEvery { helpersRepository.getNearbyHelpers(alertId) } returns Result.success(listOf(sampleHelper))
        activeAlertFlow.value = sampleAlert
        createViewModel()

        viewModel.refreshHelpers()

        assertFalse(viewModel.uiState.value.isRefreshing)
        coVerify(atLeast = 2) { helpersRepository.getNearbyHelpers(alertId) }
    }
}
