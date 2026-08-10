package com.safeher.app.core.session

import com.safeher.app.core.datastore.ActiveAlertStore
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.services.ApplicationCoroutineScope
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertSessionManager @Inject constructor(
    private val alertRepository: AlertRepository,
    private val activeAlertStore: ActiveAlertStore,
    private val applicationScope: ApplicationCoroutineScope,
) {
    private val _activeAlert = MutableStateFlow<SafetyAlert?>(null)
    val activeAlert: StateFlow<SafetyAlert?> = _activeAlert.asStateFlow()

    private val _heartbeatWarning = MutableStateFlow(false)
    val heartbeatWarning: StateFlow<Boolean> = _heartbeatWarning.asStateFlow()

    private var heartbeatJob: Job? = null
    private var consecutivePingFailures = 0
    private val restoreMutex = Mutex()
    private var hasRestoredFromServer = false

    /** True after the first [restoreActiveAlert] attempt finishes (success or failure). */
    private val _restoreAttemptFinished = MutableStateFlow(false)
    val restoreAttemptFinished: StateFlow<Boolean> = _restoreAttemptFinished.asStateFlow()

    suspend fun awaitRestoreAttempt() {
        if (_restoreAttemptFinished.value) return
        restoreAttemptFinished.first { it }
    }

    /**
     * Loads cached alert id for display only. Uses status [RESTORING_STATUS] so downstream
     * observers do not start FGS or auto-navigation until [restoreActiveAlert] confirms.
     */
    suspend fun warmStartFromCache() {
        val cachedId = activeAlertStore.activeAlertId.first() ?: return
        if (_activeAlert.value?.id == cachedId) return
        Timber.d("warmStartFromCache: cached alert id=%s (awaiting server restore)", cachedId)
        _activeAlert.value = SafetyAlert(
            id = cachedId,
            triggerType = "restored",
            latitude = null,
            longitude = null,
            status = RESTORING_STATUS,
            startedAt = "",
            endedAt = null,
            evidenceUrl = null,
        )
    }

    suspend fun restoreActiveAlert(force: Boolean = false) {
        if (hasRestoredFromServer && !force) {
            Timber.d("restoreActiveAlert: skipped (already restored)")
            _restoreAttemptFinished.update { true }
            return
        }
        restoreMutex.withLock {
            if (hasRestoredFromServer && !force) {
                _restoreAttemptFinished.update { true }
                return
            }
            try {
                Timber.d("restoreActiveAlert: fetching /alerts/active")
                alertRepository.getActiveAlert()
                    .onSuccess { alert ->
                        if (alert?.isOngoing == true) {
                            Timber.d(
                                "restoreActiveAlert: ongoing alert id=%s status=%s",
                                alert.id,
                                alert.status,
                            )
                            setActiveAlert(alert)
                            startHeartbeat(alert.id, applicationScope.scope)
                        } else {
                            Timber.d("restoreActiveAlert: no ongoing alert — clearing session")
                            clearActiveAlert()
                        }
                        hasRestoredFromServer = true
                    }
                    .onFailure { error ->
                        Timber.w(error, "restoreActiveAlert: API failed — keeping local cache state")
                    }
            } finally {
                _restoreAttemptFinished.update { true }
            }
        }
    }

    suspend fun setActiveAlert(alert: SafetyAlert) {
        Timber.d("setActiveAlert: id=%s status=%s", alert.id, alert.status)
        _activeAlert.value = alert
        activeAlertStore.saveActiveAlertId(alert.id)
    }

    suspend fun clearActiveAlert() {
        Timber.d("clearActiveAlert")
        _activeAlert.value = null
        activeAlertStore.clearActiveAlertId()
        stopHeartbeat()
    }

    fun startHeartbeat(alertId: String, scope: CoroutineScope) {
        stopHeartbeat()
        consecutivePingFailures = 0
        _heartbeatWarning.value = false
        Timber.d("startHeartbeat: alertId=%s", alertId)
        heartbeatJob = scope.launch {
            while (isActive) {
                alertRepository.pingAlert(alertId).fold(
                    onSuccess = {
                        consecutivePingFailures = 0
                        _heartbeatWarning.value = false
                    },
                    onFailure = {
                        consecutivePingFailures++
                        if (consecutivePingFailures >= HEARTBEAT_FAILURE_THRESHOLD) {
                            _heartbeatWarning.value = true
                        }
                    },
                )
                delay(HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    fun stopHeartbeat() {
        if (heartbeatJob != null) {
            Timber.d("stopHeartbeat")
        }
        heartbeatJob?.cancel()
        heartbeatJob = null
        consecutivePingFailures = 0
        _heartbeatWarning.value = false
    }

    companion object {
        const val RESTORING_STATUS = "restoring"
        const val HEARTBEAT_INTERVAL_MS = 60_000L
        const val HEARTBEAT_FAILURE_THRESHOLD = 3
    }
}
