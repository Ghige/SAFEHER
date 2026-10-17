package com.safeher.app.core.network

import com.squareup.moshi.Moshi
import retrofit2.HttpException
import java.io.IOException

object ApiErrorParser {

    private val MSG_IN_DETAIL_LIST = Regex("\"msg\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"")
    private val STRING_DETAIL = Regex("\"detail\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"")

    fun parse(throwable: Throwable, moshi: Moshi): String = when (throwable) {
        is HttpException -> parseHttpException(throwable, moshi)
        is IOException -> "Network error. Check your connection."
        else -> throwable.message ?: "Something went wrong"
    }

    private fun parseHttpException(exception: HttpException, moshi: Moshi): String {
        val body = exception.response()?.errorBody()?.string()
        if (!body.isNullOrBlank()) {
            runCatching {
                moshi.adapter(ApiErrorBody::class.java).fromJson(body)?.detail
            }.getOrNull()?.takeIf { it.isNotBlank() }?.let { return it }

            // FastAPI validation errors use detail: [{msg: "..."}] — avoid org.json
            // (unreliable under plain JVM Android unit tests).
            parseFastApiDetail(body)?.let { return it }
        }
        return when (exception.code()) {
            401 -> "Invalid phone number or password"
            403 -> "Not allowed"
            409 -> "An active alert already exists"
            429 -> "Too many requests. Please wait before trying again."
            else -> "Request failed (${exception.code()})"
        }
    }

    private fun parseFastApiDetail(body: String): String? {
        MSG_IN_DETAIL_LIST.find(body)?.groupValues?.getOrNull(1)?.let { raw ->
            return unescapeJson(raw).takeIf { it.isNotBlank() }
        }
        STRING_DETAIL.find(body)?.groupValues?.getOrNull(1)?.let { raw ->
            return unescapeJson(raw).takeIf { it.isNotBlank() }
        }
        return null
    }

    private fun unescapeJson(value: String): String =
        value.replace("\\\"", "\"").replace("\\\\", "\\").replace("\\n", "\n")
}
