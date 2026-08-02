package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.AlertResponseDto
import com.safeher.app.data.remote.dto.PingResponseDto
import com.safeher.app.data.remote.dto.TriggerAlertRequestDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface AlertsApi {

    @POST("api/v1/alerts/trigger")
    suspend fun triggerAlert(@Body body: TriggerAlertRequestDto): AlertResponseDto

    @POST("api/v1/alerts/cancel/{alert_id}")
    suspend fun cancelAlert(@Path("alert_id") alertId: String): AlertResponseDto

    @POST("api/v1/alerts/ping/{alert_id}")
    suspend fun pingAlert(@Path("alert_id") alertId: String): PingResponseDto

    @GET("api/v1/alerts/active")
    suspend fun getActiveAlert(): AlertResponseDto

    @GET("api/v1/alerts/history")
    suspend fun getHistory(): List<AlertResponseDto>
}
