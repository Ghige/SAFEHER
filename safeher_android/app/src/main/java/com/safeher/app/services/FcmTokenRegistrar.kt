package com.safeher.app.services

import com.google.firebase.messaging.FirebaseMessaging
import com.safeher.app.core.network.RetrofitDiagnostics
import com.safeher.app.core.network.SafeHerApi
import com.safeher.app.data.remote.dto.DeviceTokenRequestDto
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FcmTokenRegistrar @Inject constructor(
    private val api: SafeHerApi,
    private val applicationScope: ApplicationCoroutineScope,
) {

    fun registerCurrentToken() {
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful) {
                Timber.w(task.exception, "FCM token fetch failed")
                return@addOnCompleteListener
            }
            val token = task.result ?: return@addOnCompleteListener
            applicationScope.scope.launch {
                val path = "api/v1/users/device-token"
                RetrofitDiagnostics.logRequest(TAG, "POST", path)
                runCatching {
                    Timber.d("%s: invoking Retrofit POST %s (no NetworkMonitor gate)", TAG, path)
                    api.registerDeviceToken(DeviceTokenRequestDto(fcm_token = token))
                    RetrofitDiagnostics.logSuccess(TAG, path)
                    Timber.d("FCM token registered with backend")
                }.onFailure { error ->
                    RetrofitDiagnostics.logFailure(TAG, path, error)
                    Timber.w(error, "FCM token registration failed")
                }
            }
        }
    }

    companion object {
        private const val TAG = "FcmTokenRegistrar"
    }
}
