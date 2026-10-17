package com.safeher.app.core.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class ApiErrorParserTest {

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test
    fun parse_stringDetail() {
        val ex = httpException(400, """{"detail":"Add at least one emergency contact"}""")
        assertEquals("Add at least one emergency contact", ApiErrorParser.parse(ex, moshi))
    }

    @Test
    fun parse_validationListDetail() {
        val body =
            """{"detail":[{"type":"string_too_short","loc":["body","name"],"msg":"String should have at least 1 character","input":""}]}"""
        val ex = httpException(422, body)
        val message = ApiErrorParser.parse(ex, moshi)
        assertTrue(message.contains("at least 1 character") || message.contains("String should"))
    }

    @Test
    fun parse_409_fallback() {
        val ex = httpException(409, "{}")
        assertEquals("An active alert already exists", ApiErrorParser.parse(ex, moshi))
    }

    private fun httpException(code: Int, body: String): HttpException {
        val response = Response.error<Unit>(
            code,
            body.toResponseBody("application/json".toMediaType()),
        )
        return HttpException(response)
    }
}
