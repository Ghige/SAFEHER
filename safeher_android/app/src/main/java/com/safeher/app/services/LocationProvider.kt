package com.safeher.app.services

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Looper
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.safeher.app.domain.model.GeoCoordinates
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.cancellation.CancellationException

@Singleton
class LocationProvider @Inject constructor(
    @ApplicationContext private val context: Context,
    private val permissionManager: LocationPermissionManager,
) {
    private val fusedClient = LocationServices.getFusedLocationProviderClient(context)
    private var locationCallback: LocationCallback? = null

    @SuppressLint("MissingPermission")
    suspend fun getCurrentLocation(): GeoCoordinates? {
        if (!permissionManager.hasLocationPermission()) return null
        return try {
            val location: Location? = fusedClient.getCurrentLocation(
                Priority.PRIORITY_BALANCED_POWER_ACCURACY,
                CancellationTokenSource().token,
            ).await()
            location?.let { GeoCoordinates(it.latitude, it.longitude) }
        } catch (_: CancellationException) {
            null
        } catch (_: Exception) {
            null
        }
    }

    @SuppressLint("MissingPermission")
    fun locationUpdates(): Flow<GeoCoordinates> = callbackFlow {
        if (!permissionManager.hasLocationPermission()) {
            close(IllegalStateException("Location permission not granted"))
            return@callbackFlow
        }

        val request = LocationRequest.Builder(
            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            UPDATE_INTERVAL_MS,
        )
            .setMinUpdateIntervalMillis(MIN_UPDATE_INTERVAL_MS)
            .setMaxUpdateDelayMillis(MAX_UPDATE_DELAY_MS)
            .build()

        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { location ->
                    trySend(GeoCoordinates(location.latitude, location.longitude))
                }
            }
        }
        locationCallback = callback

        fusedClient.requestLocationUpdates(
            request,
            callback,
            Looper.getMainLooper(),
        )

        awaitClose {
            fusedClient.removeLocationUpdates(callback)
            if (locationCallback === callback) {
                locationCallback = null
            }
        }
    }

    fun stopLocationUpdates() {
        locationCallback?.let { callback ->
            fusedClient.removeLocationUpdates(callback)
            locationCallback = null
        }
    }

    companion object {
        const val UPDATE_INTERVAL_MS = 7_000L
        const val MIN_UPDATE_INTERVAL_MS = 5_000L
        const val MAX_UPDATE_DELAY_MS = 10_000L
    }
}
