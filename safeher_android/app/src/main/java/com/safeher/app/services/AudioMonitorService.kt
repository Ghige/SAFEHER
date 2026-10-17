package com.safeher.app.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.safeher.app.MainActivity
import com.safeher.app.R
import com.safeher.app.services.ai.AiDetectionLogger
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import timber.log.Timber
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
        if (intent == null) {
            Timber.w("AudioMonitorService restarted with null intent — recovering")
            try {
                startForegroundWithMicrophoneType()
            } catch (e: Exception) {
                audioMonitoringLauncher.onServiceStopped()
                stopSelf()
                return START_NOT_STICKY
            }
            if (!audioPermissionManager.hasRecordAudioPermission() ||
                !audioMonitoringLauncher.isRunning.value
            ) {
                stopMonitoringInternal()
                return START_NOT_STICKY
            }
            startMonitoringLoop()
            return START_STICKY
        }
        when (intent.action) {
            ACTION_STOP -> {
                stopMonitoringInternal()
                return START_NOT_STICKY
            }
            ACTION_PAUSE_MIC -> {
                pauseMicCapture()
                return START_STICKY
            }
            ACTION_RESUME_MIC -> {
                if (audioMonitoringLauncher.isRunning.value &&
                    audioPermissionManager.hasRecordAudioPermission()
                ) {
                    startMonitoringLoop()
                }
                return START_STICKY
            }
            ACTION_START -> {
                // Enter foreground before any validation/async work (FGS timeout rule).
                startForegroundWithMicrophoneType()
                if (!audioPermissionManager.hasRecordAudioPermission()) {
                    stopMonitoringInternal()
                    return START_NOT_STICKY
                }
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
        if (monitorJob?.isActive == true) return
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
                Timber.e("AudioRecord failed to initialize")
                stopMonitoringInternal()
                return@launch
            }
            audioRecord = record
            record.startRecording()
            Timber.d("AudioRecord started (continuous distress capture)")
            AiDetectionLogger.liveCaptureResume(
                resumeTs = System.currentTimeMillis(),
                nextSequence = aiSensorState.nextWindowSequence(),
            )

            val readBuffer = ShortArray(bufferSize)
            val inferenceWindow = ShortArray(INFERENCE_WINDOW_SAMPLES)
            var windowFill = 0
            while (isActive) {
                val read = record.read(readBuffer, 0, readBuffer.size)
                if (read > 0) {
                    val slice = readBuffer.copyOf(read)
                    val rms = computeRms(slice)
                    aiSensorState.updateAudioLevel((rms / MAX_RMS).coerceIn(0f, 1f))
                    for (i in 0 until read) {
                        inferenceWindow[windowFill++] = readBuffer[i]
                        if (windowFill >= INFERENCE_WINDOW_SAMPLES) {
                            aiSensorState.updateAudioBuffer(inferenceWindow.copyOf())
                            windowFill = 0
                        }
                    }
                }
                delay(SAMPLE_INTERVAL_MS)
            }
        }
    }

    /** Release mic for a short ASR slot without tearing down the FGS notification. */
    private fun pauseMicCapture() {
        Timber.i("Pausing AudioRecord for ASR interleave slot")
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

    private fun startForegroundWithMicrophoneType() {
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
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
        private const val ACTION_PAUSE_MIC = "com.safeher.app.action.AI_AUDIO_PAUSE_MIC"
        private const val ACTION_RESUME_MIC = "com.safeher.app.action.AI_AUDIO_RESUME_MIC"
        private const val CHANNEL_ID = "safeher_ai_monitoring"
        private const val NOTIFICATION_ID = 2001
        private const val SAMPLE_RATE = 16_000
        private const val INFERENCE_WINDOW_SAMPLES = 16_000
        private const val SAMPLE_INTERVAL_MS = 500L
        private const val MAX_RMS = 0.25f

        fun createStartIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_START)

        fun createStopIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_STOP)

        fun createPauseMicIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_PAUSE_MIC)

        fun createResumeMicIntent(context: Context): Intent =
            Intent(context, AudioMonitorService::class.java).setAction(ACTION_RESUME_MIC)
    }
}
