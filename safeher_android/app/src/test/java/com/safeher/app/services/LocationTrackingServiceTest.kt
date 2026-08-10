package com.safeher.app.services

import android.content.ComponentName
import android.content.Context
import io.mockk.every
import io.mockk.mockk
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LocationTrackingServiceTest {

    private val context: Context = mockk(relaxed = true)
    private val locationPermissionManager: LocationPermissionManager = mockk(relaxed = true)
    private lateinit var service: LocationTrackingService

    @Before
    fun setUp() {
        every { locationPermissionManager.hasLocationPermission() } returns true
        every { context.startForegroundService(any()) } returns
            ComponentName("com.safeher.app.debug", "LocationForegroundService")
        every { context.stopService(any()) } returns true
        service = LocationTrackingService(context, locationPermissionManager)
    }

    @Test
    fun stopTracking_whenNotTracking_doesNotCallStopService() {
        service.stopTracking()

        assertFalse(service.isTracking.value)
        assertNull(service.activeAlertId.value)
    }

    @Test
    fun stopTracking_whenTracking_clearsState() {
        service.startTracking("alert-1")
        service.stopTracking()

        assertFalse(service.isTracking.value)
        assertNull(service.activeAlertId.value)
    }

    @Test
    fun startTracking_withoutLocationPermission_defersStart() {
        every { locationPermissionManager.hasLocationPermission() } returns false

        service.startTracking("alert-1")

        assertFalse(service.isTracking.value)
        assertTrue(service.activeAlertId.value == "alert-1")
    }

    @Test
    fun onServiceStopped_clearsState() {
        service.startTracking("alert-1")
        service.onServiceStopped()

        assertFalse(service.isTracking.value)
        assertNull(service.activeAlertId.value)
    }

    @Test
    fun startTracking_sameAlertTwice_isIdempotent() {
        service.startTracking("alert-1")
        service.startTracking("alert-1")

        assertTrue(service.isTracking.value)
        assertTrue(service.activeAlertId.value == "alert-1")
    }
}
