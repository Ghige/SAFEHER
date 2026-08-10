package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.DeviceTokenRequestDto
import com.safeher.app.data.remote.dto.LoginRequestDto
import com.safeher.app.data.remote.dto.MessageResponseDto
import com.safeher.app.data.remote.dto.OtpVerifyRequestDto
import com.safeher.app.data.remote.dto.RegisterRequestDto
import com.safeher.app.data.remote.dto.SendOtpRequestDto
import com.safeher.app.data.remote.dto.TokenResponseDto
import com.safeher.app.data.remote.dto.UserProfileDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface SafeHerApi {

    @POST("api/v1/auth/register")
    suspend fun register(@Body body: RegisterRequestDto): TokenResponseDto

    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequestDto): TokenResponseDto

    @POST("api/v1/auth/send-otp")
    suspend fun sendOtp(@Body body: SendOtpRequestDto): MessageResponseDto

    @POST("api/v1/auth/verify-otp")
    suspend fun verifyOtp(@Body body: OtpVerifyRequestDto): MessageResponseDto

    @GET("api/v1/users/profile")
    suspend fun getProfile(): UserProfileDto

    @POST("api/v1/users/device-token")
    suspend fun registerDeviceToken(@Body body: DeviceTokenRequestDto)
}
