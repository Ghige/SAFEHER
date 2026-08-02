package com.safeher.app.domain.model

data class TrackLink(
    val trackUrl: String,
    val expiresInHours: Int,
)

data class LiveLocation(
    val alertId: String,
    val latitude: Double?,
    val longitude: Double?,
    val status: String,
    val startedAt: String,
    val mapsEmbed: String?,
)

data class GeoCoordinates(
    val latitude: Double,
    val longitude: Double,
)
