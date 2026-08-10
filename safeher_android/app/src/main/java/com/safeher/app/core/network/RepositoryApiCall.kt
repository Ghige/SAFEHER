package com.safeher.app.core.network

import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import timber.log.Timber

object RepositoryApiCall {

    suspend inline fun <T> execute(moshi: Moshi, block: () -> T): Result<T> = try {
        Result.success(block())
    } catch (e: Exception) {
        Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
    }

    suspend inline fun <T> executeOnline(
        moshi: Moshi,
        networkMonitor: NetworkMonitor,
        block: () -> T,
    ): Result<T> = try {
        val isOnline = networkMonitor.isOnline.first()
        Timber.d("RepositoryApiCall.executeOnline: isOnline.first()=%s", isOnline)
        if (!isOnline) {
            Result.failure(Exception("You are offline. Connect to the internet and try again."))
        } else {
            Result.success(block())
        }
    } catch (e: Exception) {
        Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
    }
}
