package com.safeher.app.di

import com.safeher.app.services.ai.AudioInferenceEngine
import com.safeher.app.services.ai.MissingMovementInferenceEngine
import com.safeher.app.services.ai.MovementInferenceEngine
import com.safeher.app.services.ai.TfliteAudioInferenceEngine
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class AiInferenceModule {

    @Binds
    @Singleton
    abstract fun bindAudioInferenceEngine(impl: TfliteAudioInferenceEngine): AudioInferenceEngine

    @Binds
    @Singleton
    abstract fun bindMovementInferenceEngine(impl: MissingMovementInferenceEngine): MovementInferenceEngine
}
