package com.safeher.app.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.safeher.app.MainActivity
import com.safeher.app.R
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.abs
import kotlin.math.sqrt

@AndroidEntryPoint
class AudioMonitorService : Service() {

    @Inject lateinit var audioPermissionManager: AudioPermissionManager
    @Inject lateinit var aiSensorState: AiSensorState
    @Inject lateinit var audioMonitoringLauncher: AudioMonitoringLauncher
    @Inject lateinit var serviceScope: ServiceCoroutineScope

    private var monitorJob: Job? = null
    private var audioRecord: AudioRecord? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopMonitoringInternal()
                return START_NOT_STICKY
            }
            ACTION_START -> {
                startForeground(NOTIFICATION_ID, buildNotification())
                startMonitoringLoop()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopMonitoringInternal()
        super.onDestroy()
    }

    private fun startMonitoringLoop() {
        if (!audioPermissionManager.hasRecordAudioPermission()) {
            stopMonitoringInternal()
            return
        }
        monitorJob?.cancel()
        monitorJob = serviceScope.scope.launch {
            val bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            ).coerceAtLeast(SAMPLE_RATE)

            val record = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                stopMonitoringInternal()
                return@launch
            }
            audioRecord = record
            record.startRecording()

            val buffer = ShortArray(bufferSize)
            while (isActive) {
                val read = record.read(buffer, 0, buffer.size)
                if (read > 0) {
                    val slice = buffer.copyOf(read)
                    val rms = computeRms(slice)
                    aiSensorState.updateAudioLevel((rms / MAX_RMS).coerceIn(0f, 1f))
                    aiSensorState.updateAudioBuffer(slice)
                }
                delay(SAMPLE_INTERVAL_MS)
            }
        }
    }

    private fun stopMonitoringInternal() {
        monitorJob?.cancel()
        monitorJob = null
        audioRecord?.run {
            try {
                stop()
            } catch (_: IllegalStateException) {
            }
            release()
        }
        audioRecord = null
        aiSensorState.updateAudioLevel(0f)
        audioMonitoringLauncher.onServiceStopped()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun computeRms(samples: ShortArray): Float {
        if (samples.isEmpty()) return 0f
        var sum = 0.0
        for (sample in samples) {
            val normalized = sample / Short.MAX_VALUE.toFloat()
            sum += normalized * normalized
        }
        return sqrt(sum / samples.size).toFloat()
    }

    private fun buildNotification(): Notification {
        createChannel()
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.ai_notification_title))
            .setContentText(getString(R.string.ai_notification_body))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.ai_notification_channel),
            NotificationManager.IMPORTANCE_LOW,
        )
        manager.createNotificationChannel(channel)
    }

    companion object {
        private const val ACTION_START = "com.safeher.app.action.AI_AUDIO_START"
        private const val ACTION_STOP = "com.safeher.app.action.AI_AUDIO_STOP"
        private const val CHANNEL_ID = "safeher_ai_monitoring"
        private const val NOTIFICATION_ID = 2001
        private const val SAMPLE_RATE = 16_000
        private const val SAMPLE_INTERVAL_MS = 500L
        private const val MAX_RMS = 0.25f

        fun createStartIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_START)

        fun createStopIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_STOP)
    }
}
