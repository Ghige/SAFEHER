package com.safeher.app.data.remote.dto

/**
 * DELETE /api/v1/users/contacts/{contact_id} returns **204 No Content**.
 * This type documents successful deletion on the client; no response body is parsed.
 */
data class DeleteContactResponseDto(
    val deleted: Boolean = true,
)
