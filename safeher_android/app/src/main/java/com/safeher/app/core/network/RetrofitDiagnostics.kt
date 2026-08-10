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
                val errorBody = throwable.response()?.errorBody()?.string()
                Timber.e(
                    throwable,
                    "%s: <-- HttpException path=%s status=%d errorBody=%s",
                    tag,
                    path,
                    throwable.code(),
                    errorBody,
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
