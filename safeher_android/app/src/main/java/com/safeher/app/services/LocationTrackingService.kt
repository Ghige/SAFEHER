package com.safeher.app.services

import android.app.BackgroundServiceStartNotAllowedException
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationTrackingService @Inject constructor(
    @ApplicationContext private val context: Context,
    private val locationPermissionManager: LocationPermissionManager,
) {
    private val _isTracking = MutableStateFlow(false)
    val isTracking: StateFlow<Boolean> = _isTracking.asStateFlow()

    private val _activeAlertId = MutableStateFlow<String?>(null)
    val activeAlertId: StateFlow<String?> = _activeAlertId.asStateFlow()

    /** Alert to start tracking once location permission is granted or app is foreground. */
    private var pendingStartAlertId: String? = null

    fun startTracking(alertId: String) {
        if (_activeAlertId.value == alertId && _isTracking.value) return

        _activeAlertId.value = alertId

        if (!locationPermissionManager.hasLocationPermission()) {
            Timber.w("Location permission missing — deferring SOS location tracking for alert %s", alertId)
            pendingStartAlertId = alertId
            _isTracking.value = false
            return
        }

        pendingStartAlertId = null
        _isTracking.value = true
        if (!startForegroundService(createStartIntent(alertId))) {
            pendingStartAlertId = alertId
            _isTracking.value = false
        }
    }

    fun stopTracking() {
        pendingStartAlertId = null
        if (!_isTracking.value && _activeAlertId.value == null) return
        _isTracking.value = false
        _activeAlertId.value = null
        stopRunningService()
    }

    /**
     * Starts deferred tracking when the app returns to foreground or location permission is granted.
     */
    fun flushPendingStart() {
        val alertId = pendingStartAlertId ?: return
        if (!locationPermissionManager.hasLocationPermission()) return
        startTracking(alertId)
    }

    fun onServiceStopped() {
        _isTracking.value = false
        _activeAlertId.value = null
        pendingStartAlertId = null
    }

    private fun createStartIntent(alertId: String): Intent =
        LocationForegroundService.createStartIntent(context, alertId)

    private fun startForegroundService(intent: Intent): Boolean {
        return try {
            ContextCompat.startForegroundService(context, intent)
            true
        } catch (e: IllegalStateException) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
                e is BackgroundServiceStartNotAllowedException
            ) {
                Timber.w(e, "Deferring location FGS until app is in foreground")
                false
            } else {
                Timber.e(e, "Failed to start location FGS")
                _isTracking.value = false
                _activeAlertId.value = null
                false
            }
        }
    }

    private fun stopRunningService() {
        val stopIntent = LocationForegroundService.createStopIntent(context)
        try {
            context.stopService(stopIntent)
        } catch (e: Exception) {
            Timber.w(e, "Failed to stop location FGS")
        }
    }
}
