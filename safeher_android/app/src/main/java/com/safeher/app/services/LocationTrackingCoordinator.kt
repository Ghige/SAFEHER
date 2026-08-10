package com.safeher.app.services

import com.safeher.app.core.session.AlertSessionManager
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationTrackingCoordinator @Inject constructor(
    private val alertSessionManager: AlertSessionManager,
    private val locationTrackingService: LocationTrackingService,
    private val applicationScope: ApplicationCoroutineScope,
) {

    private var started = false

    fun startObserving() {
        if (started) return
        started = true
        applicationScope.scope.launch {
            alertSessionManager.activeAlert
                .distinctUntilChanged { old, new -> old?.id == new?.id && old?.isOngoing == new?.isOngoing }
                .collect { alert ->
                    if (alert?.isOngoing == true) {
                        locationTrackingService.startTracking(alert.id)
                    } else {
                        locationTrackingService.stopTracking()
                    }
                }
        }
    }
}

@Singleton
class ApplicationCoroutineScope @Inject constructor() {
    val scope: CoroutineScope = CoroutineScope(
        SupervisorJob() + CoroutineExceptionHandler { _, throwable ->
            Timber.e(throwable, "Uncaught exception in application coroutine scope")
        },
    )
}

@Singleton
class ServiceCoroutineScope @Inject constructor() {
    val scope: CoroutineScope = CoroutineScope(
        SupervisorJob() + CoroutineExceptionHandler { _, throwable ->
            Timber.e(throwable, "Uncaught exception in service coroutine scope")
        },
    )
}
