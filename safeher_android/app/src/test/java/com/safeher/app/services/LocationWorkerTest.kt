package com.safeher.app.services

import android.content.Context
import androidx.work.Data
import androidx.work.ListenableWorker
import androidx.work.WorkerParameters
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.LocationRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.util.concurrent.Executor

class LocationWorkerTest {

    private val locationRepository: LocationRepository = mockk()
    private val alertSessionManager: AlertSessionManager = mockk()
    private val activeAlertFlow = MutableStateFlow<SafetyAlert?>(null)
    private val context: Context = mockk(relaxed = true)

    private val ongoingAlert = SafetyAlert(
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
        every { alertSessionManager.activeAlert } returns activeAlertFlow
    }

    @Test
    fun doWork_alertNotOngoing_skipsPostAndSucceeds() = runTest {
        activeAlertFlow.value = ongoingAlert.copy(status = "cancelled")
        val worker = createWorker(
            alertId = "alert-uuid-123",
            latitude = 12.97,
            longitude = 77.59,
        )

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success()::class, result::class)
        coVerify(exactly = 0) { locationRepository.updateLocation(any(), any(), any()) }
    }

    @Test
    fun doWork_alertOngoing_postsLocation() = runTest {
        activeAlertFlow.value = ongoingAlert
        coEvery {
            locationRepository.updateLocation("alert-uuid-123", 12.97, 77.59)
        } returns Result.success(Unit)
        val worker = createWorker(
            alertId = "alert-uuid-123",
            latitude = 12.97,
            longitude = 77.59,
        )

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success()::class, result::class)
        coVerify {
            locationRepository.updateLocation("alert-uuid-123", 12.97, 77.59)
        }
    }

    private fun createWorker(alertId: String, latitude: Double, longitude: Double): LocationWorker {
        val inputData = Data.Builder()
            .putString("alert_id", alertId)
            .putDouble("latitude", latitude)
            .putDouble("longitude", longitude)
            .build()
        val params = mockk<WorkerParameters>(relaxed = true)
        every { params.inputData } returns inputData
        every { params.runAttemptCount } returns 0
        every { params.backgroundExecutor } returns Executor { it.run() }
        return LocationWorker(context, params, locationRepository, alertSessionManager)
    }
}
