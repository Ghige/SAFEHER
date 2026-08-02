package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.LiveLocationResponseDto
import com.safeher.app.data.remote.dto.LocationUpdateRequestDto
import com.safeher.app.data.remote.dto.LocationUpdateResponseDto
import com.safeher.app.data.remote.dto.TrackLinkResponseDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface LocationApi {

    @POST("api/v1/location/update")
    suspend fun updateLocation(@Body body: LocationUpdateRequestDto): LocationUpdateResponseDto

    @GET("api/v1/location/track-link/{alert_id}")
    suspend fun getTrackLink(@Path("alert_id") alertId: String): TrackLinkResponseDto

    @GET("api/v1/location/live")
    suspend fun getLiveLocation(@Query("token") token: String): LiveLocationResponseDto
}
