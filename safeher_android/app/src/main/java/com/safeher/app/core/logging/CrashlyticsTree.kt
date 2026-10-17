package com.safeher.app.core.logging

import android.util.Log
import com.google.firebase.crashlytics.FirebaseCrashlytics
import timber.log.Timber

/**
 * Release Timber tree — forwards WARN+ to Crashlytics as non-fatals.
 * Does not log secrets; only message + throwable.
 */
class CrashlyticsTree : Timber.Tree() {
    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        if (priority < Log.WARN) return
        val crashlytics = FirebaseCrashlytics.getInstance()
        crashlytics.log("${tag.orEmpty()}: $message")
        if (t != null) {
            crashlytics.recordException(t)
        } else if (priority >= Log.ERROR) {
            crashlytics.recordException(RuntimeException(message))
        }
    }
}
