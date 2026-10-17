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
class AudioMonitoringLauncher @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    private var pendingStart = false

    fun startMonitoring() {
        if (_isRunning.value) return
        pendingStart = false
        _isRunning.value = true
        if (!startForegroundService(AudioMonitorService.createStartIntent(context))) {
            // Mirror LocationTrackingService: clear running so flushPendingStart can retry.
            pendingStart = true
            _isRunning.value = false
        }
    }

    fun stopMonitoring() {
        pendingStart = false
        if (!_isRunning.value) return
        _isRunning.value = false
        stopRunningService()
    }

    /** Brief mic release for duty-cycled ASR (FGS stays up). */
    fun pauseMicCapture() {
        if (!_isRunning.value) return
        try {
            context.startService(AudioMonitorService.createPauseMicIntent(context))
        } catch (e: Exception) {
            Timber.w(e, "pauseMicCapture failed")
        }
    }

    fun resumeMicCapture() {
        if (!_isRunning.value) return
        try {
            context.startService(AudioMonitorService.createResumeMicIntent(context))
        } catch (e: Exception) {
            Timber.w(e, "resumeMicCapture failed")
        }
    }

    fun flushPendingStart() {
        if (!pendingStart) return
        pendingStart = false
        startMonitoring()
    }

    fun onServiceStopped() {
        _isRunning.value = false
        pendingStart = false
    }

    private fun startForegroundService(intent: Intent): Boolean {
        return try {
            ContextCompat.startForegroundService(context, intent)
            true
        } catch (e: IllegalStateException) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
                e is BackgroundServiceStartNotAllowedException
            ) {
                Timber.w(e, "Deferring audio monitor FGS until app is in foreground")
                false
            } else {
                Timber.e(e, "Failed to start audio monitor FGS")
                false
            }
        }
    }

    private fun stopRunningService() {
        try {
            context.stopService(AudioMonitorService.createStopIntent(context))
        } catch (e: Exception) {
            Timber.w(e, "Failed to stop audio monitor FGS")
        }
    }
}
