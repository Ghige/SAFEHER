package com.safeher.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.safeher.app.core.firebase.FirebaseBootstrap
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.services.AiMonitoringCoordinator
import com.safeher.app.services.ApplicationCoroutineScope
import com.safeher.app.services.FcmTokenRegistrar
import com.safeher.app.services.LocationTrackingCoordinator
import com.safeher.app.services.NotificationChannelManager
import com.safeher.app.services.SosTriggerWorker
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@HiltAndroidApp
class SafeHerApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory
    @Inject lateinit var locationTrackingCoordinator: LocationTrackingCoordinator
    @Inject lateinit var aiMonitoringCoordinator: AiMonitoringCoordinator
    @Inject lateinit var notificationChannelManager: NotificationChannelManager
    @Inject lateinit var alertSessionManager: AlertSessionManager
    @Inject lateinit var applicationScope: ApplicationCoroutineScope
    @Inject lateinit var fcmTokenRegistrar: FcmTokenRegistrar

    override fun onCreate() {
        super.onCreate()
        FirebaseBootstrap.initialize(this)
        if (BuildConfig.ENABLE_LOGGING) {
            Timber.plant(Timber.DebugTree())
        }
        notificationChannelManager.ensureChannelsCreated()
        fcmTokenRegistrar.registerCurrentToken()
        aiMonitoringCoordinator.startObserving()
        applicationScope.scope.launch {
            alertSessionManager.warmStartFromCache()
            alertSessionManager.restoreActiveAlert()
            locationTrackingCoordinator.startObserving()
            SosTriggerWorker.enqueueFlush(this@SafeHerApp)
        }
    }

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
}
