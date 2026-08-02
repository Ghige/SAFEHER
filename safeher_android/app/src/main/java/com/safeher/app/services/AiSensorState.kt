package com.safeher.app.services

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AiSensorState @Inject constructor() {
    private val _audioLevel = MutableStateFlow(0f)
    val audioLevel: StateFlow<Float> = _audioLevel.asStateFlow()

    private val _movementLevel = MutableStateFlow(0f)
    val movementLevel: StateFlow<Float> = _movementLevel.asStateFlow()

    private val _latestAudioBuffer = MutableStateFlow<ShortArray?>(null)
    val latestAudioBuffer: StateFlow<ShortArray?> = _latestAudioBuffer.asStateFlow()

    private val _latestAccelerometerWindow = MutableStateFlow<FloatArray?>(null)
    val latestAccelerometerWindow: StateFlow<FloatArray?> = _latestAccelerometerWindow.asStateFlow()

    fun updateAudioLevel(level: Float) {
        _audioLevel.value = level.coerceIn(0f, 1f)
    }

    fun updateMovementLevel(level: Float) {
        _movementLevel.value = level.coerceIn(0f, 1f)
    }

    fun updateAudioBuffer(buffer: ShortArray) {
        _latestAudioBuffer.value = buffer
    }

    fun updateAccelerometerWindow(window: FloatArray) {
        _latestAccelerometerWindow.value = window
    }

    fun reset() {
        _audioLevel.value = 0f
        _movementLevel.value = 0f
        _latestAudioBuffer.value = null
        _latestAccelerometerWindow.value = null
    }
}
