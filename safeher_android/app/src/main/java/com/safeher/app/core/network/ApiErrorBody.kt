package com.safeher.app.core.network

import com.squareup.moshi.JsonClass

/**
 * Standard FastAPI error body: `{ "detail": "..." }`.
 */
@JsonClass(generateAdapter = true)
data class ApiErrorBody(
    val detail: String? = null,
)
