package com.safeher.app.di

import com.safeher.app.services.SosTriggerScheduler
import com.safeher.app.services.SosTriggerSchedulerImpl
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class ServiceModule {

    @Binds
    @Singleton
    abstract fun bindSosTriggerScheduler(impl: SosTriggerSchedulerImpl): SosTriggerScheduler
}
