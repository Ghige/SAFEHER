package com.safeher.app.services

import com.safeher.app.core.datastore.AiSettingsStore
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.AiAction
import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.domain.model.AiTriggerSource
import com.safeher.app.domain.model.SensorScores
import com.safeher.app.domain.repository.AiRepository
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.services.ai.AudioInferenceEngine
import com.safeher.app.services.ai.MovementInferenceEngine
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Calendar
import javax.inject.Inject
import javax.inject.Singleton

sealed interface AiCoordinatorEvent {
    data object NavigateToSosCountdown : AiCoordinatorEvent
    data object NavigateToActiveAlert : AiCoordinatorEvent
}

@Singleton
class AiMonitoringCoordinator @Inject constructor(
    private val aiRepository: AiRepository,
    private val alertRepository: AlertRepository,
    private val alertSessionManager: AlertSessionManager,
    private val aiSettingsStore: AiSettingsStore,
    private val audioInferenceEngine: AudioInferenceEngine,
    private val movementInferenceEngine: MovementInferenceEngine,
    private val audioMonitoringLauncher: AudioMonitoringLauncher,
    private val movementMonitorService: MovementMonitorService,
    private val aiSensorState: AiSensorState,
    private val locationProvider: LocationProvider,
    private val applicationScope: ApplicationCoroutineScope,
) {
    private val _isMonitoring = MutableStateFlow(false)
    val isMonitoring: StateFlow<Boolean> = _isMonitoring.asStateFlow()

    private val _isAppInForeground = MutableStateFlow(true)
    val isAppInForeground: StateFlow<Boolean> = _isAppInForeground.asStateFlow()

    private val _confidence = MutableStateFlow<AiConfidenceResult?>(null)
    val confidence: StateFlow<AiConfidenceResult?> = _confidence.asStateFlow()

    private val _isLoadingConfidence = MutableStateFlow(false)
    val isLoadingConfidence: StateFlow<Boolean> = _isLoadingConfidence.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _modelsAvailable = MutableStateFlow(false)
    val modelsAvailable: StateFlow<Boolean> = _modelsAvailable.asStateFlow()

    private val _isIsolated = MutableStateFlow(false)
    val isIsolated: StateFlow<Boolean> = _isIsolated.asStateFlow()

    private val _events = MutableSharedFlow<AiCoordinatorEvent>()
    val events: SharedFlow<AiCoordinatorEvent> = _events.asSharedFlow()

    val audioLevel = aiSensorState.audioLevel
    val movementLevel = aiSensorState.movementLevel

    private var inferenceJob: Job? = null
    private var lastSensorScores: SensorScores? = null
    private var lastTriggerSource = AiTriggerSource.AUDIO
    private var started = false

    fun startObserving() {
        if (started) return
        started = true
        _modelsAvailable.value = audioInferenceEngine.isAvailable && movementInferenceEngine.isAvailable

        applicationScope.scope.launch {
            aiSettingsStore.monitoringEnabled.collect { enabled ->
                if (enabled) {
                    startMonitoringInternal()
                } else {
                    stopMonitoringInternal()
                }
            }
        }

        applicationScope.scope.launch {
            aiSettingsStore.isIsolated.collect { isolated ->
                _isIsolated.value = isolated
            }
        }

        applicationScope.scope.launch {
            var hadOngoingAlert = false
            alertSessionManager.activeAlert.collect { alert ->
                val ongoing = alert?.isOngoing == true
                if (hadOngoingAlert && !ongoing) {
                    aiSettingsStore.setMonitoringEnabled(false)
                }
                hadOngoingAlert = ongoing
            }
        }
    }

    fun setAppInForeground(inForeground: Boolean) {
        _isAppInForeground.value = inForeground
        if (inForeground && _isMonitoring.value) {
            startInferenceLoop()
        } else {
            stopInferenceLoop()
        }
    }

    suspend fun setMonitoringEnabled(enabled: Boolean) {
        aiSettingsStore.setMonitoringEnabled(enabled)
    }

    suspend fun setIsIsolated(isolated: Boolean) {
        aiSettingsStore.setIsIsolated(isolated)
    }

    fun stopMonitoring() {
        applicationScope.scope.launch {
            aiSettingsStore.setMonitoringEnabled(false)
        }
    }

    fun refreshConfidence() {
        val scores = lastSensorScores ?: return
        if (!scores.hasAnyScore) return
        applicationScope.scope.launch {
            queryConfidence(scores)
        }
    }

    fun clearError() {
        _error.value = null
    }

    private suspend fun startMonitoringInternal() {
        if (_isMonitoring.value) return
        _isMonitoring.value = true
        audioMonitoringLauncher.startMonitoring()
        movementMonitorService.startMonitoring()
        if (_isAppInForeground.value) {
            startInferenceLoop()
        }
    }

    private fun stopMonitoringInternal() {
        if (!_isMonitoring.value) return
        _isMonitoring.value = false
        stopInferenceLoop()
        audioMonitoringLauncher.stopMonitoring()
        movementMonitorService.stopMonitoring()
        aiSensorState.reset()
        _confidence.value = null
        lastSensorScores = null
    }

    private fun startInferenceLoop() {
        if (!_modelsAvailable.value) return
        if (inferenceJob?.isActive == true) return
        inferenceJob = applicationScope.scope.launch {
            while (isActive && _isMonitoring.value && _isAppInForeground.value) {
                runInferenceCycle()
                delay(INFERENCE_INTERVAL_MS)
            }
        }
    }

    private fun stopInferenceLoop() {
        inferenceJob?.cancel()
        inferenceJob = null
    }

    private suspend fun runInferenceCycle() {
        val audioBuffer = aiSensorState.latestAudioBuffer.value ?: return
        val accelWindow = aiSensorState.latestAccelerometerWindow.value

        var audioScore: Double? = null
        var movementScore: Double? = null
        var fallDetected = false

        if (audioInferenceEngine.isAvailable) {
            audioScore = audioInferenceEngine.inferDistressScore(audioBuffer, AUDIO_SAMPLE_RATE)
        }
        if (movementInferenceEngine.isAvailable && accelWindow != null) {
            movementInferenceEngine.inferMovement(accelWindow)?.let { result ->
                movementScore = result.movementScore
                fallDetected = result.fallDetected
            }
        }

        val scores = SensorScores(
            audioScore = audioScore,
            movementScore = movementScore,
            fallDetected = fallDetected,
        )
        if (!scores.hasAnyScore) return

        lastSensorScores = scores
        lastTriggerSource = when {
            fallDetected -> AiTriggerSource.MOVEMENT
            (audioScore ?: 0.0) >= (movementScore ?: 0.0) -> AiTriggerSource.AUDIO
            else -> AiTriggerSource.MOVEMENT
        }

        if (fallDetected && movementScore != null) {
            handleMovementSos(scores)
            return
        }

        queryConfidence(scores)
    }

    private suspend fun queryConfidence(scores: SensorScores) {
        _isLoadingConfidence.value = true
        _error.value = null
        val result = aiRepository.getConfidence(
            audioScore = scores.audioScore?.toFloat() ?: 0f,
            movementScore = scores.movementScore?.toFloat() ?: 0f,
            isNight = isNightHour(),
            isIsolated = _isIsolated.value,
        )
        _isLoadingConfidence.value = false
        result.fold(
            onSuccess = { confidenceResult ->
                _confidence.value = confidenceResult
                handleConfidenceAction(confidenceResult, scores)
            },
            onFailure = { error ->
                _error.value = error.message
            },
        )
    }

    private suspend fun handleConfidenceAction(
        confidenceResult: AiConfidenceResult,
        scores: SensorScores,
    ) {
        when (confidenceResult.action) {
            AiAction.FIRE_IMMEDIATELY -> when (lastTriggerSource) {
                AiTriggerSource.AUDIO -> handleAudioSos(scores)
                AiTriggerSource.MOVEMENT -> handleMovementSos(scores)
            }
            AiAction.CONFIRM_30S -> _events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            AiAction.SILENT_VIBRATION, AiAction.NOTHING -> Unit
        }
    }

    private suspend fun handleAudioSos(scores: SensorScores) {
        val coords = locationProvider.getCurrentLocation()
        val result = aiRepository.triggerAudioSos(
            audioScore = scores.audioScore?.toFloat() ?: 0f,
            movementScore = scores.movementScore?.toFloat() ?: 0f,
            latitude = coords?.latitude?.toFloat(),
            longitude = coords?.longitude?.toFloat(),
            isNight = isNightHour(),
            isIsolated = _isIsolated.value,
        )
        handleSosResult(result)
    }

    private suspend fun handleMovementSos(scores: SensorScores) {
        val coords = locationProvider.getCurrentLocation()
        val result = aiRepository.triggerMovementSos(
            movementScore = scores.movementScore?.toFloat() ?: 0f,
            fallDetected = scores.fallDetected,
            audioScore = scores.audioScore?.toFloat() ?: 0f,
            latitude = coords?.latitude?.toFloat(),
            longitude = coords?.longitude?.toFloat(),
            isNight = isNightHour(),
            isIsolated = _isIsolated.value,
        )
        handleSosResult(result)
    }

    private suspend fun handleSosResult(result: Result<com.safeher.app.domain.model.AiSosResult>) {
        result.fold(
            onSuccess = { sosResult ->
                if (sosResult.triggerError != null) {
                    _error.value = sosResult.triggerError
                }
                sosResult.fusion?.let { _confidence.value = it }
                if (sosResult.alertId != null) {
                    alertRepository.getActiveAlert().onSuccess { alert ->
                        if (alert != null) {
                            alertSessionManager.setActiveAlert(alert)
                            alertSessionManager.startHeartbeat(alert.id, applicationScope.scope)
                            _events.emit(AiCoordinatorEvent.NavigateToActiveAlert)
                        }
                    }
                }
            },
            onFailure = { error ->
                _error.value = error.message
            },
        )
    }

    private fun isNightHour(): Boolean {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return hour >= 22 || hour < 6
    }

    companion object {
        private const val INFERENCE_INTERVAL_MS = 3_000L
        private const val AUDIO_SAMPLE_RATE = 16_000
    }
}
