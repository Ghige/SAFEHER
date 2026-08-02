package com.safeher.app.core.network

import com.safeher.app.BuildConfig
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideMoshi(): Moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        unauthorizedInterceptor: UnauthorizedInterceptor,
    ): OkHttpClient =
        buildOkHttpClient(
            authInterceptor = authInterceptor,
            unauthorizedInterceptor = unauthorizedInterceptor,
            enableLogging = BuildConfig.ENABLE_LOGGING,
        )

    @Provides
    @Singleton
    fun provideSafeHerApi(retrofitClient: RetrofitClient): SafeHerApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideContactsApi(retrofitClient: RetrofitClient): ContactsApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideAlertsApi(retrofitClient: RetrofitClient): AlertsApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideLocationApi(retrofitClient: RetrofitClient): LocationApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideHelpersApi(retrofitClient: RetrofitClient): HelpersApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideAiApi(retrofitClient: RetrofitClient): AiApi =
        retrofitClient.createService()

    @Provides
    @Singleton
    fun provideRetrofitClient(
        okHttpClient: OkHttpClient,
        moshi: Moshi,
    ): RetrofitClient = RetrofitClient(okHttpClient, moshi)
}
