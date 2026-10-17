package com.safeher.app.core.network

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

/**
 * Release builds talk only to HTTPS hosts. Local emulator URLs are refused.
 * Does not send SOS. Does not log Authorization headers.
 */
class ReleaseNetworkPolicyInterceptor(
    private val enforceHttps: Boolean,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        if (!enforceHttps) {
            return chain.proceed(chain.request())
        }
        val url = chain.request().url
        if (!url.isHttps) {
            throw IOException(
                "SafeHer release builds require HTTPS. Cannot reach ${url.scheme}://${url.host}.",
            )
        }
        if (url.host in BLOCKED_HOSTS) {
            throw IOException(
                "SafeHer release builds cannot use a development host (${url.host}).",
            )
        }
        return chain.proceed(chain.request())
    }

    companion object {
        val BLOCKED_HOSTS = setOf(
            "10.0.2.2",
            "10.0.3.2",
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
        )
    }
}
