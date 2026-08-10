package com.safeher.app.services

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.safeher.app.MainActivity
import com.safeher.app.R
import dagger.hilt.android.AndroidEntryPoint
import timber.log.Timber
import javax.inject.Inject

@AndroidEntryPoint
class SafeHerFirebaseMessagingService : FirebaseMessagingService() {

    @Inject lateinit var notificationChannelManager: NotificationChannelManager
    @Inject lateinit var fcmTokenRegistrar: FcmTokenRegistrar

    override fun onCreate() {
        super.onCreate()
        notificationChannelManager.ensureChannelsCreated()
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Timber.d("FCM token refreshed")
        fcmTokenRegistrar.registerCurrentToken()
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val title = message.notification?.title ?: getString(R.string.fcm_default_title)
        val body = message.notification?.body ?: return
        showNotification(title, body)
    }

    private fun showNotification(title: String, body: String) {
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, NotificationChannelManager.FCM_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(body)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(FCM_NOTIFICATION_ID, notification)
    }

    companion object {
        private const val FCM_NOTIFICATION_ID = 3001
    }
}
