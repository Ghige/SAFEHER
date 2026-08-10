package com.safeher.app.core.network

import com.safeher.app.core.session.SessionCleanupManager
import com.safeher.app.services.ApplicationCoroutineScope
import dagger.Lazy
import kotlinx.coroutines.launch
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Clears the session when an authenticated request receives HTTP 401.
 */
@Singleton
class UnauthorizedInterceptor @Inject constructor(
    private val sessionCleanupManager: Lazy<SessionCleanupManager>,
    private val applicationScope: ApplicationCoroutineScope,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)
        if (response.code == 401 && request.header("Authorization") != null) {
            applicationScope.scope.launch {
                sessionCleanupManager.get().performSessionExpired()
            }
        }
        return response
    }
}
