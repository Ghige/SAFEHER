package com.safeher.app.data.repository

import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.LocationApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.data.remote.dto.LiveLocationResponseDto
import com.safeher.app.data.remote.dto.LocationUpdateRequestDto
import com.safeher.app.data.remote.dto.TrackLinkResponseDto
import com.safeher.app.domain.model.LiveLocation
import com.safeher.app.domain.model.TrackLink
import com.safeher.app.domain.repository.LocationRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationRepositoryImpl @Inject constructor(
    private val api: LocationApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : LocationRepository {

    override suspend fun updateLocation(
        alertId: String,
        latitude: Double,
        longitude: Double,
    ): Result<Unit> = RepositoryApiCall.executeOnline(moshi, networkMonitor) {
        api.updateLocation(
            LocationUpdateRequestDto(
                alert_id = alertId,
                latitude = latitude,
                longitude = longitude,
            ),
        )
        Unit
    }

    override suspend fun getTrackLink(alertId: String): Result<TrackLink> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.getTrackLink(alertId).toDomain()
        }

    override suspend fun getLiveLocation(token: String): Result<LiveLocation> =
        RepositoryApiCall.execute(moshi) {
            api.getLiveLocation(token).toDomain()
        }

    private fun TrackLinkResponseDto.toDomain() = TrackLink(
        trackUrl = track_url,
        expiresInHours = expires_in_hours,
    )

    private fun LiveLocationResponseDto.toDomain() = LiveLocation(
        alertId = alert_id,
        latitude = latitude,
        longitude = longitude,
        status = status,
        startedAt = started_at,
        mapsEmbed = maps_embed,
    )
}
