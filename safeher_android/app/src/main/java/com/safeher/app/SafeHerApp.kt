package com.safeher.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.LocationTrackingCoordinator
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber
import javax.inject.Inject

@HiltAndroidApp
class SafeHerApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory
    @Inject lateinit var locationTrackingCoordinator: LocationTrackingCoordinator
    @Inject lateinit var aiMonitoringCoordinator: AiMonitoringCoordinator

    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.ENABLE_LOGGING) {
            Timber.plant(Timber.DebugTree())
        }
        locationTrackingCoordinator.startObserving()
        aiMonitoringCoordinator.startObserving()
    }

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
}
