package com.safeher.app.services

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.sqrt

@Singleton
class MovementMonitorService @Inject constructor(
    @ApplicationContext private val context: Context,
    private val aiSensorState: AiSensorState,
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    private val window = FloatArray(WINDOW_SIZE * 3)
    private var windowIndex = 0
    private var windowFilled = false

    fun startMonitoring() {
        if (_isRunning.value || accelerometer == null) return
        windowIndex = 0
        windowFilled = false
        sensorManager.registerListener(
            this,
            accelerometer,
            SensorManager.SENSOR_DELAY_NORMAL,
        )
        _isRunning.value = true
    }

    fun stopMonitoring() {
        if (!_isRunning.value) return
        sensorManager.unregisterListener(this)
        _isRunning.value = false
        windowIndex = 0
        windowFilled = false
        aiSensorState.updateMovementLevel(0f)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event?.sensor?.type != Sensor.TYPE_ACCELEROMETER) return
        val magnitude = sqrt(
            event.values[0] * event.values[0] +
                event.values[1] * event.values[1] +
                event.values[2] * event.values[2],
        )
        val normalized = ((magnitude - GRAVITY) / MAX_DELTA).coerceIn(0f, 1f)
        aiSensorState.updateMovementLevel(normalized)

        val base = windowIndex * 3
        window[base] = event.values[0]
        window[base + 1] = event.values[1]
        window[base + 2] = event.values[2]
        windowIndex = (windowIndex + 1) % WINDOW_SIZE
        if (windowIndex == 0) windowFilled = true

        if (windowFilled) {
            aiSensorState.updateAccelerometerWindow(window.copyOf())
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    companion object {
        private const val WINDOW_SIZE = 128
        private const val GRAVITY = 9.81f
        private const val MAX_DELTA = 15f
    }
}
