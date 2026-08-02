package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.NearbyHelperDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface HelpersApi {

    @GET("api/v1/helpers/nearby")
    suspend fun getNearbyHelpers(@Query("alert_id") alertId: String): List<NearbyHelperDto>

    @POST("api/v1/helpers/respond/{alert_id}")
    suspend fun respondToAlert(@Path("alert_id") alertId: String): NearbyHelperDto

    @POST("api/v1/helpers/block/{helper_id}")
    suspend fun blockHelper(@Path("helper_id") helperId: String): Response<Unit>
}
