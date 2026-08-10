package com.safeher.app.services

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NotificationChannelManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val notificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    fun ensureChannelsCreated() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        listOf(
            NotificationChannelSpec(
                id = LOCATION_CHANNEL_ID,
                name = "Live Location",
                importance = NotificationManager.IMPORTANCE_HIGH,
            ),
            NotificationChannelSpec(
                id = AI_CHANNEL_ID,
                name = "AI Monitoring",
                importance = NotificationManager.IMPORTANCE_LOW,
            ),
            NotificationChannelSpec(
                id = FCM_CHANNEL_ID,
                name = "Push Notifications",
                importance = NotificationManager.IMPORTANCE_HIGH,
            ),
        ).forEach { spec ->
            if (notificationManager.getNotificationChannel(spec.id) == null) {
                val channel = NotificationChannel(spec.id, spec.name, spec.importance)
                notificationManager.createNotificationChannel(channel)
            }
        }
    }

    private data class NotificationChannelSpec(
        val id: String,
        val name: String,
        val importance: Int,
    )

    companion object {
        const val LOCATION_CHANNEL_ID = "safeher_location_tracking"
        const val AI_CHANNEL_ID = "safeher_ai_monitoring"
        const val FCM_CHANNEL_ID = "safeher_fcm"
    }
}
