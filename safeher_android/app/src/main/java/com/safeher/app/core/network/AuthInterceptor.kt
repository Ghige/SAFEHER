package com.safeher.app.core.network

import com.safeher.app.core.datastore.SecureTokenStore
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Attaches `Authorization: Bearer <token>` when a session token exists.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val secureTokenStore: SecureTokenStore,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = secureTokenStore.getAccessTokenSync()
        val request = if (!token.isNullOrBlank()) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}
