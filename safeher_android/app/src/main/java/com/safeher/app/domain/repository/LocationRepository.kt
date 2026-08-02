package com.safeher.app.domain.repository

import com.safeher.app.domain.model.LiveLocation
import com.safeher.app.domain.model.TrackLink

interface LocationRepository {

    suspend fun updateLocation(alertId: String, latitude: Double, longitude: Double): Result<Unit>

    suspend fun getTrackLink(alertId: String): Result<TrackLink>

    suspend fun getLiveLocation(token: String): Result<LiveLocation>
}
