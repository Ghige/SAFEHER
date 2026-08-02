package com.safeher.app.core.session

import com.safeher.app.core.datastore.ActiveAlertStore
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertSessionManager @Inject constructor(
    private val alertRepository: AlertRepository,
    private val activeAlertStore: ActiveAlertStore,
) {
    private val _activeAlert = MutableStateFlow<SafetyAlert?>(null)
    val activeAlert: StateFlow<SafetyAlert?> = _activeAlert.asStateFlow()

    private var heartbeatJob: Job? = null

    suspend fun restoreActiveAlert() {
        alertRepository.getActiveAlert().onSuccess { alert ->
            if (alert?.isOngoing == true) {
                setActiveAlert(alert)
            } else {
                clearActiveAlert()
            }
        }
    }

    suspend fun setActiveAlert(alert: SafetyAlert) {
        _activeAlert.value = alert
        activeAlertStore.saveActiveAlertId(alert.id)
    }

    suspend fun clearActiveAlert() {
        _activeAlert.value = null
        activeAlertStore.clearActiveAlertId()
        stopHeartbeat()
    }

    fun startHeartbeat(alertId: String, scope: CoroutineScope) {
        stopHeartbeat()
        heartbeatJob = scope.launch {
            while (isActive) {
                alertRepository.pingAlert(alertId)
                delay(HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    companion object {
        const val HEARTBEAT_INTERVAL_MS = 60_000L
    }
}
