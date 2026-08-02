package com.safeher.app.data.remote.dto

import com.squareup.moshi.JsonClass

/**
 * Reserved for future request-body support. Current backend uses path-only respond.
 */
@JsonClass(generateAdapter = true)
data class HelperResponseRequestDto(
    val action: String,
)
