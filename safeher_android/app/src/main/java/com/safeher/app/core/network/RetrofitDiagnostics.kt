package com.safeher.app.core.network

import com.safeher.app.BuildConfig
import retrofit2.HttpException
import timber.log.Timber

/**
 * Diagnostic logging for Retrofit calls during network troubleshooting.
 * Does not alter request/response behavior.
 */
object RetrofitDiagnostics {

    fun logRequest(tag: String, method: String, path: String) {
        Timber.d("%s: --> %s %s%s", tag, method, BuildConfig.BASE_URL, path)
    }

    fun logSuccess(tag: String, path: String) {
        Timber.d("%s: <-- success %s", tag, path)
    }

    fun logOfflineGate(tag: String, path: String, isOnline: Boolean) {
        Timber.w(
            "%s: offline gate blocked request isOnline=%s path=%s (Retrofit NOT invoked)",
            tag,
            isOnline,
            path,
        )
    }

    fun logFailure(tag: String, path: String, throwable: Throwable) {
        when (throwable) {
            is HttpException -> {
                // Do not read errorBody() here — it can only be consumed once (ApiErrorParser needs it).
                Timber.e(
                    throwable,
                    "%s: <-- HttpException path=%s status=%d",
                    tag,
                    path,
                    throwable.code(),
                )
            }
            else -> Timber.e(
                throwable,
                "%s: <-- %s path=%s message=%s",
                tag,
                throwable.javaClass.name,
                path,
                throwable.message,
            )
        }
    }
}
