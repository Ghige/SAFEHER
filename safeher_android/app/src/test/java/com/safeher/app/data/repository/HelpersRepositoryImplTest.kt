package com.safeher.app.data.repository

import com.safeher.app.core.network.HelpersApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.NearbyHelperDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class HelpersRepositoryImplTest {

    private val api: HelpersApi = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: HelpersRepositoryImpl

    private val alertId = "550e8400-e29b-41d4-a716-446655440000"
    private val helperId = "660e8400-e29b-41d4-a716-446655440001"

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        repository = HelpersRepositoryImpl(api, networkMonitor, moshi)
    }

    @Test
    fun getNearbyHelpers_mapsDtoToDomain() = runTest {
        coEvery { api.getNearbyHelpers(alertId) } returns listOf(
            NearbyHelperDto(
                id = helperId,
                alert_id = alertId,
                status = "notified",
                notified_at = "2026-08-02T10:00:00Z",
                identity_revealed = true,
                approved_by_user = false,
                name = "Alex",
                phone_number = "9876543210",
            ),
        )

        val result = repository.getNearbyHelpers(alertId)

        assertTrue(result.isSuccess)
        val helper = result.getOrNull()!!.first()
        assertEquals(helperId, helper.id)
        assertEquals(alertId, helper.alertId)
        assertEquals("notified", helper.status)
        assertEquals("Alex", helper.name)
    }

    @Test
    fun respondToAlert_callsApiWithBackendAlertId() = runTest {
        coEvery { api.respondToAlert(alertId) } returns NearbyHelperDto(
            id = helperId,
            alert_id = alertId,
            status = "responding",
            notified_at = "2026-08-02T10:00:00Z",
            identity_revealed = true,
            approved_by_user = true,
            name = "Alex",
        )

        val result = repository.respondToAlert(alertId)

        assertTrue(result.isSuccess)
        assertEquals("responding", result.getOrNull()!!.status)
        coVerify { api.respondToAlert(alertId) }
    }

    @Test
    fun blockHelper_usesBackendHelperId() = runTest {
        coEvery { api.blockHelper(helperId) } returns Response.success(Unit)

        val result = repository.blockHelper(helperId)

        assertTrue(result.isSuccess)
        coVerify { api.blockHelper(helperId) }
    }

    @Test
    fun blockHelper_httpError_returnsFailure() = runTest {
        coEvery { api.blockHelper(helperId) } returns Response.error(
            403,
            """{"detail":"Forbidden"}""".toResponseBody(),
        )

        val result = repository.blockHelper(helperId)

        assertTrue(result.isFailure)
    }

    @Test
    fun getNearbyHelpers_offline_returnsFailure() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.getNearbyHelpers(alertId)

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("offline", ignoreCase = true) == true)
    }
}
