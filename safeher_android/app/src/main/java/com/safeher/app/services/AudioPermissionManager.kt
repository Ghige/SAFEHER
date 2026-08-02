package com.safeher.app.services

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

enum class AudioPermissionStatus {
    GRANTED,
    DENIED,
    PERMANENTLY_DENIED,
}

@Singleton
class AudioPermissionManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    fun hasRecordAudioPermission(): Boolean =
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED

    fun getPermissionStatus(shouldShowRationale: Boolean): AudioPermissionStatus {
        return when {
            hasRecordAudioPermission() -> AudioPermissionStatus.GRANTED
            shouldShowRationale -> AudioPermissionStatus.DENIED
            else -> AudioPermissionStatus.PERMANENTLY_DENIED
        }
    }

    fun createAppSettingsIntent(): Intent =
        Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.fromParts("package", context.packageName, null),
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
}
