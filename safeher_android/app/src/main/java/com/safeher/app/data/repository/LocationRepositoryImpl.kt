package com.safeher.app.data.repository

import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.LocationApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.LiveLocationResponseDto
import com.safeher.app.data.remote.dto.LocationUpdateRequestDto
import com.safeher.app.data.remote.dto.TrackLinkResponseDto
import com.safeher.app.domain.model.LiveLocation
import com.safeher.app.domain.model.TrackLink
import com.safeher.app.domain.repository.LocationRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
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
    ): Result<Unit> = apiCall {
        api.updateLocation(
            LocationUpdateRequestDto(
                alert_id = alertId,
                latitude = latitude,
                longitude = longitude,
            ),
        )
        Unit
    }

    override suspend fun getTrackLink(alertId: String): Result<TrackLink> = apiCall {
        api.getTrackLink(alertId).toDomain()
    }

    override suspend fun getLiveLocation(token: String): Result<LiveLocation> = publicApiCall {
        api.getLiveLocation(token).toDomain()
    }

    private suspend inline fun <T> apiCall(block: () -> T): Result<T> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                Result.failure(Exception("You are offline. Connect to the internet and try again."))
            } else {
                Result.success(block())
            }
        } catch (e: HttpException) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }

    private inline fun <T> publicApiCall(block: () -> T): Result<T> {
        return try {
            Result.success(block())
        } catch (e: HttpException) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
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
