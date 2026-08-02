package com.safeher.app.services

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationTrackingService @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val _isTracking = MutableStateFlow(false)
    val isTracking: StateFlow<Boolean> = _isTracking.asStateFlow()

    private val _activeAlertId = MutableStateFlow<String?>(null)
    val activeAlertId: StateFlow<String?> = _activeAlertId.asStateFlow()

    fun startTracking(alertId: String) {
        if (_activeAlertId.value == alertId && _isTracking.value) return
        _activeAlertId.value = alertId
        _isTracking.value = true
        val intent = LocationForegroundService.createStartIntent(context, alertId)
        ContextCompat.startForegroundService(context, intent)
    }

    fun stopTracking() {
        _isTracking.value = false
        _activeAlertId.value = null
        context.startService(LocationForegroundService.createStopIntent(context))
    }

    fun onServiceStopped() {
        _isTracking.value = false
        _activeAlertId.value = null
    }
}
