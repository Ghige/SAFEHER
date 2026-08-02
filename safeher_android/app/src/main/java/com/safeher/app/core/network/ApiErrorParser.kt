package com.safeher.app.core.network

import com.squareup.moshi.Moshi
import retrofit2.HttpException
import java.io.IOException

object ApiErrorParser {

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
            }.getOrNull()?.let { return it }
        }
        return when (exception.code()) {
            401 -> "Invalid phone number or password"
            429 -> "Too many requests. Please wait before trying again."
            else -> "Request failed (${exception.code()})"
        }
    }
}
