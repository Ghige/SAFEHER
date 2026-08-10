package com.safeher.app.data.repository

import com.safeher.app.core.datastore.PendingSosStore
import com.safeher.app.core.network.AlertsApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.AlertResponseDto
import com.safeher.app.data.remote.dto.TriggerAlertRequestDto
import com.safeher.app.services.SosTriggerScheduler
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class AlertRepositoryImplTest {

    private val api: AlertsApi = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val pendingSosStore: PendingSosStore = mockk(relaxed = true)
    private val sosTriggerScheduler: SosTriggerScheduler = mockk(relaxed = true)
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: AlertRepositoryImpl

    private val alertDto = AlertResponseDto(
        id = "alert-uuid-123",
        trigger_type = "manual",
        latitude = 12.97,
        longitude = 77.59,
        status = "active",
        started_at = "2026-08-02T10:00:00Z",
        ended_at = null,
        evidence_url = null,
    )

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        every { pendingSosStore.hasPending } returns flowOf(false)
        repository = AlertRepositoryImpl(api, networkMonitor, moshi, pendingSosStore, sosTriggerScheduler)
    }

    @Test
    fun triggerAlert_mapsDtoToDomain() = runTest {
        coEvery { api.triggerAlert(any()) } returns alertDto

        val result = repository.triggerAlert(12.97, 77.59)

        assertTrue(result.isSuccess)
        assertEquals("alert-uuid-123", result.getOrNull()!!.id)
        coVerify {
            api.triggerAlert(
                TriggerAlertRequestDto(
                    trigger_type = "manual",
                    latitude = 12.97,
                    longitude = 77.59,
                ),
            )
        }
    }

    @Test
    fun triggerAlert_withoutLocation_sendsNullCoords() = runTest {
        coEvery { api.triggerAlert(any()) } returns alertDto

        repository.triggerAlert(null, null)

        coVerify {
            api.triggerAlert(
                TriggerAlertRequestDto(
                    trigger_type = "manual",
                    latitude = null,
                    longitude = null,
                ),
            )
        }
    }

    @Test
    fun cancelAlert_callsApiWithAlertId() = runTest {
        coEvery { api.cancelAlert("alert-uuid-123") } returns alertDto.copy(status = "cancelled")

        val result = repository.cancelAlert("alert-uuid-123")

        assertTrue(result.isSuccess)
        assertEquals("cancelled", result.getOrNull()!!.status)
    }

    @Test
    fun pingAlert_callsApiWithAlertId() = runTest {
        coEvery { api.pingAlert("alert-uuid-123") } returns mockk(relaxed = true)

        val result = repository.pingAlert("alert-uuid-123")

        assertTrue(result.isSuccess)
        coVerify { api.pingAlert("alert-uuid-123") }
    }

    @Test
    fun getActiveAlert_returnsNullOn404() = runTest {
        val response = Response.error<AlertResponseDto>(
            404,
            "{}".toResponseBody("application/json".toMediaType()),
        )
        coEvery { api.getActiveAlert() } throws HttpException(response)

        val result = repository.getActiveAlert()

        assertTrue(result.isSuccess)
        assertNull(result.getOrNull())
    }

    @Test
    fun getHistory_mapsList() = runTest {
        coEvery { api.getHistory() } returns listOf(alertDto)

        val result = repository.getHistory()

        assertTrue(result.isSuccess)
        assertEquals(1, result.getOrNull()!!.size)
    }

    @Test
    fun triggerAlert_offline_queuesAndReturnsQueuedException() = runTest {
        coEvery { pendingSosStore.save(any()) } returns Unit
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.triggerAlert(12.97, 77.59)

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is OfflineSosQueuedException)
        coVerify { pendingSosStore.save(any()) }
        verify { sosTriggerScheduler.scheduleFlush() }
    }
}
