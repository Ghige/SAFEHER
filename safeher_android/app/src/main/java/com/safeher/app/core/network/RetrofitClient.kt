package com.safeher.app.core.network

import com.safeher.app.BuildConfig
import com.squareup.moshi.Moshi
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RetrofitClient @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val moshi: Moshi,
) {

    val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }

    inline fun <reified T> createService(): T = retrofit.create(T::class.java)

    companion object {
        const val CONNECT_TIMEOUT_SECONDS = 30L
        const val READ_TIMEOUT_SECONDS = 30L
        const val WRITE_TIMEOUT_SECONDS = 30L
    }
}

fun buildOkHttpClient(
    authInterceptor: AuthInterceptor,
    unauthorizedInterceptor: UnauthorizedInterceptor,
    enableLogging: Boolean,
): OkHttpClient {
    val builder = OkHttpClient.Builder()
        .connectTimeout(RetrofitClient.CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(RetrofitClient.READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(RetrofitClient.WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .addInterceptor(authInterceptor)
        .addInterceptor(unauthorizedInterceptor)

    if (enableLogging) {
        val logging = okhttp3.logging.HttpLoggingInterceptor().apply {
            level = okhttp3.logging.HttpLoggingInterceptor.Level.BASIC
            redactHeader("Authorization")
        }
        builder.addInterceptor(logging)
    }

    return builder.build()
}
