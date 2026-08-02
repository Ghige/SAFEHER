package com.safeher.app.di

import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent

/**
 * Root Hilt module. Network bindings live in [com.safeher.app.core.network.NetworkModule].
 * Feature repository modules will be added in later tasks.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModules
