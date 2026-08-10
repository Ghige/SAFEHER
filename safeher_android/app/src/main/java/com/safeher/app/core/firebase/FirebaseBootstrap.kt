package com.safeher.app.core.firebase

import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.crashlytics.FirebaseCrashlytics
import com.safeher.app.BuildConfig

/**
 * Initializes Firebase SDKs once at application startup.
 */
object FirebaseBootstrap {

    fun initialize(context: Context) {
        if (FirebaseApp.getApps(context).isEmpty()) {
            FirebaseApp.initializeApp(context)
        }

        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = !BuildConfig.ENABLE_LOGGING
    }
}
