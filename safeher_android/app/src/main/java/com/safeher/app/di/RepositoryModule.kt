package com.safeher.app.di

import com.safeher.app.data.repository.AlertRepositoryImpl
import com.safeher.app.data.repository.AuthRepositoryImpl
import com.safeher.app.data.repository.ContactsRepositoryImpl
import com.safeher.app.data.repository.UserRepositoryImpl
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.domain.repository.AuthRepository
import com.safeher.app.domain.repository.ContactsRepository
import com.safeher.app.domain.repository.UserRepository
import com.safeher.app.data.repository.AiRepositoryImpl
import com.safeher.app.data.repository.HelpersRepositoryImpl
import com.safeher.app.data.repository.LocationRepositoryImpl
import com.safeher.app.domain.repository.AiRepository
import com.safeher.app.domain.repository.HelpersRepository
import com.safeher.app.domain.repository.LocationRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindAuthRepository(impl: AuthRepositoryImpl): AuthRepository

    @Binds
    @Singleton
    abstract fun bindUserRepository(impl: UserRepositoryImpl): UserRepository

    @Binds
    @Singleton
    abstract fun bindContactsRepository(impl: ContactsRepositoryImpl): ContactsRepository

    @Binds
    @Singleton
    abstract fun bindAlertRepository(impl: AlertRepositoryImpl): AlertRepository

    @Binds
    @Singleton
    abstract fun bindLocationRepository(impl: LocationRepositoryImpl): LocationRepository

    @Binds
    @Singleton
    abstract fun bindHelpersRepository(impl: HelpersRepositoryImpl): HelpersRepository

    @Binds
    @Singleton
    abstract fun bindAiRepository(impl: AiRepositoryImpl): AiRepository
}
