package com.safeher.app.core.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.IOException
import java.util.concurrent.TimeUnit

class ReleaseNetworkPolicyInterceptorTest {

    @Test
    fun httpsProductionHost_allowed() {
        val code = execute("https://api.safeher.app/api/v1/ping/", enforceHttps = true)
        assertEquals(404, code)
    }

    @Test
    fun httpEmulatorHost_blockedInRelease() {
        try {
            execute("http://10.0.2.2:8000/api/v1/ping/", enforceHttps = true)
            fail("Expected IOException")
        } catch (e: IOException) {
            assertTrue(e.message!!.contains("HTTPS") || e.message!!.contains("development host"))
        }
    }

    @Test
    fun localhost_blockedInRelease() {
        try {
            execute("https://localhost/api/v1/ping/", enforceHttps = true)
            fail("Expected IOException")
        } catch (e: IOException) {
            assertTrue(e.message!!.contains("development host"))
        }
    }

    @Test
    fun httpAllowedWhenNotEnforced() {
        val code = execute("http://10.0.2.2:8000/api/v1/ping/", enforceHttps = false)
        assertEquals(404, code)
    }

    private fun execute(url: String, enforceHttps: Boolean): Int {
        val client = OkHttpClient.Builder()
            .addInterceptor(ReleaseNetworkPolicyInterceptor(enforceHttps))
            .addInterceptor { chain ->
                okhttp3.Response.Builder()
                    .request(chain.request())
                    .protocol(okhttp3.Protocol.HTTP_1_1)
                    .code(404)
                    .message("stub")
                    .body(ByteArray(0).toResponseBody("text/plain".toMediaType()))
                    .build()
            }
            .callTimeout(5, TimeUnit.SECONDS)
            .build()
        val request = Request.Builder().url(url).build()
        return client.newCall(request).execute().use { it.code }
    }
}
