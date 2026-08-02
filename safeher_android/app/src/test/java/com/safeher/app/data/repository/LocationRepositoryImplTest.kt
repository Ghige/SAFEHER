package com.safeher.app.data.repository

import com.safeher.app.core.network.LocationApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.LocationUpdateRequestDto
import com.safeher.app.data.remote.dto.TrackLinkResponseDto
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

class LocationRepositoryImplTest {

    private val api: LocationApi = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: LocationRepositoryImpl

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        repository = LocationRepositoryImpl(api, networkMonitor, moshi)
    }

    @Test
    fun updateLocation_callsApiWithAlertId() = runTest {
        coEvery { api.updateLocation(any()) } returns mockk(relaxed = true)

        val result = repository.updateLocation("alert-uuid-123", 12.97, 77.59)

        assertTrue(result.isSuccess)
        coVerify {
            api.updateLocation(
                LocationUpdateRequestDto(
                    alert_id = "alert-uuid-123",
                    latitude = 12.97,
                    longitude = 77.59,
                ),
            )
        }
    }

    @Test
    fun getTrackLink_mapsDtoToDomain() = runTest {
        coEvery { api.getTrackLink("alert-uuid-123") } returns TrackLinkResponseDto(
            track_url = "https://safeher.app/track?token=abc",
            expires_in_hours = 24,
        )

        val result = repository.getTrackLink("alert-uuid-123")

        assertTrue(result.isSuccess)
        assertEquals("https://safeher.app/track?token=abc", result.getOrNull()!!.trackUrl)
        assertEquals(24, result.getOrNull()!!.expiresInHours)
    }

    @Test
    fun updateLocation_offline_returnsFailure() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.updateLocation("alert-uuid-123", 12.97, 77.59)

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()!!.message!!.contains("offline", ignoreCase = true))
    }
}
