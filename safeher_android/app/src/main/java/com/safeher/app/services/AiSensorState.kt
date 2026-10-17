package com.safeher.app.services

import com.safeher.app.services.ai.AiDetectionLogger
import com.safeher.app.services.ai.CompletedAudioWindow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.ArrayDeque
import java.util.concurrent.atomic.AtomicLong
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

    private val windowLock = Any()
    private val pendingWindows = ArrayDeque<CompletedAudioWindow>()
    private val windowSequence = AtomicLong(0)
    private val droppedWindowCount = AtomicLong(0)

    fun pendingCompletedWindowCount(): Int = synchronized(windowLock) { pendingWindows.size }

    fun droppedCompletedWindowCount(): Long = droppedWindowCount.get()

    /** Sequence that the next completed window will receive. Does not log PCM. */
    fun nextWindowSequence(): Long = windowSequence.get() + 1L

    fun updateAudioLevel(level: Float) {
        _audioLevel.value = level.coerceIn(0f, 1f)
    }

    fun updateMovementLevel(level: Float) {
        _movementLevel.value = level.coerceIn(0f, 1f)
    }

    fun updateAudioBuffer(buffer: ShortArray) {
        val window = CompletedAudioWindow(
            sequence = windowSequence.incrementAndGet(),
            timestampMs = System.currentTimeMillis(),
            sampleCount = buffer.size,
            sampleRateHz = CompletedAudioWindow.PRODUCTION_SAMPLE_RATE_HZ,
            samples = buffer,
        )
        synchronized(windowLock) {
            while (pendingWindows.size >= MAX_PENDING_WINDOWS) {
                pendingWindows.removeFirst()
                droppedWindowCount.incrementAndGet()
            }
            pendingWindows.addLast(window)
        }
        _latestAudioBuffer.value = buffer
        AiDetectionLogger.liveWindowCreated(
            sequence = window.sequence,
            timestampMs = window.timestampMs,
            sampleCount = window.sampleCount,
            sampleRateHz = window.sampleRateHz,
        )
    }

    /** Consume the next completed 1-second window. Does not re-score stale buffers. */
    fun pollCompletedWindow(): CompletedAudioWindow? = synchronized(windowLock) {
        if (pendingWindows.isEmpty()) null else pendingWindows.removeFirst()
    }

    fun updateAccelerometerWindow(window: FloatArray) {
        _latestAccelerometerWindow.value = window
    }

    fun reset() {
        _audioLevel.value = 0f
        _movementLevel.value = 0f
        _latestAudioBuffer.value = null
        _latestAccelerometerWindow.value = null
        synchronized(windowLock) {
            pendingWindows.clear()
        }
        windowSequence.set(0)
        droppedWindowCount.set(0)
    }

    companion object {
        const val MAX_PENDING_WINDOWS = 4
    }
}
