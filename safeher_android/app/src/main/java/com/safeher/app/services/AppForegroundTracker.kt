package com.safeher.app.services

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AppForegroundTracker @Inject constructor(
    private val aiMonitoringCoordinator: AiMonitoringCoordinator,
    private val locationTrackingService: LocationTrackingService,
    private val audioMonitoringLauncher: AudioMonitoringLauncher,
) : DefaultLifecycleObserver {

    private var registered = false

    fun register() {
        if (registered) return
        registered = true
        Timber.d("AppForegroundTracker.register")
        ProcessLifecycleOwner.get().lifecycle.addObserver(this)
    }

    override fun onStart(owner: LifecycleOwner) {
        Timber.d("AppForegroundTracker.onStart (app foreground)")
        aiMonitoringCoordinator.setAppInForeground(true)
        locationTrackingService.flushPendingStart()
        audioMonitoringLauncher.flushPendingStart()
    }

    override fun onStop(owner: LifecycleOwner) {
        Timber.d("AppForegroundTracker.onStop (app background)")
        aiMonitoringCoordinator.setAppInForeground(false)
    }
}
