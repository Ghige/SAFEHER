package com.safeher.app.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.safeher.app.MainActivity
import com.safeher.app.R
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.repository.LocationRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class LocationForegroundService : Service() {

    @Inject lateinit var locationRepository: LocationRepository
    @Inject lateinit var locationProvider: LocationProvider
    @Inject lateinit var permissionManager: LocationPermissionManager
    @Inject lateinit var locationTrackingService: LocationTrackingService
    @Inject lateinit var alertSessionManager: AlertSessionManager
    @Inject lateinit var serviceScope: ServiceCoroutineScope

    private var trackingJob: Job? = null
    private var alertId: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopTrackingInternal()
                return START_NOT_STICKY
            }
            ACTION_START -> {
                val id = intent.getStringExtra(EXTRA_ALERT_ID)
                if (id.isNullOrBlank()) {
                    stopSelf()
                    return START_NOT_STICKY
                }
                alertId = id
                startForeground(NOTIFICATION_ID, buildNotification())
                startTrackingLoop(id)
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopTrackingInternal()
        super.onDestroy()
    }

    private fun startTrackingLoop(activeAlertId: String) {
        trackingJob?.cancel()
        trackingJob = serviceScope.scope.launch {
            while (isActive) {
                val alert = alertSessionManager.activeAlert.value
                if (alert == null || !alert.isOngoing || alert.id != activeAlertId) {
                    stopTrackingInternal()
                    break
                }
                if (!permissionManager.hasLocationPermission()) {
                    delay(UPDATE_LOOP_DELAY_MS)
                    continue
                }
                val coords = locationProvider.getCurrentLocation()
                if (coords != null) {
                    val result = locationRepository.updateLocation(
                        activeAlertId,
                        coords.latitude,
                        coords.longitude,
                    )
                    if (result.isFailure) {
                        val message = result.exceptionOrNull()?.message.orEmpty()
                        if (message.contains("offline", ignoreCase = true)) {
                            LocationWorker.enqueueRetry(
                                this@LocationForegroundService,
                                activeAlertId,
                                coords.latitude,
                                coords.longitude,
                            )
                        } else if (message.contains("not found", ignoreCase = true) ||
                            message.contains("401", ignoreCase = true)
                        ) {
                            stopTrackingInternal()
                            return@launch
                        }
                    }
                }
                delay(UPDATE_LOOP_DELAY_MS)
            }
        }
    }

    private fun stopTrackingInternal() {
        trackingJob?.cancel()
        trackingJob = null
        locationProvider.stopLocationUpdates()
        locationTrackingService.onServiceStopped()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun buildNotification(): Notification {
        createNotificationChannel()
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.location_notification_title))
            .setContentText(getString(R.string.location_notification_body))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.location_notification_channel),
            NotificationManager.IMPORTANCE_HIGH,
        )
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    companion object {
        private const val CHANNEL_ID = "safeher_location_tracking"
        private const val NOTIFICATION_ID = 1001
        private const val EXTRA_ALERT_ID = "extra_alert_id"
        private const val ACTION_START = "com.safeher.app.action.START_LOCATION"
        private const val ACTION_STOP = "com.safeher.app.action.STOP_LOCATION"
        const val UPDATE_LOOP_DELAY_MS = 7_000L

        fun createStartIntent(context: Context, alertId: String): Intent =
            Intent(context, LocationForegroundService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_ALERT_ID, alertId)
            }

        fun createStopIntent(context: Context): Intent =
            Intent(context, LocationForegroundService::class.java).apply {
                action = ACTION_STOP
            }
    }
}
