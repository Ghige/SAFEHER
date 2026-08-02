package com.safeher.app.services

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AudioMonitoringLauncher @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    fun startMonitoring() {
        if (_isRunning.value) return
        _isRunning.value = true
        val intent = AudioMonitorService.createStartIntent(context)
        ContextCompat.startForegroundService(context, intent)
    }

    fun stopMonitoring() {
        if (!_isRunning.value) return
        _isRunning.value = false
        context.startService(AudioMonitorService.createStopIntent(context))
    }

    fun onServiceStopped() {
        _isRunning.value = false
    }
}
