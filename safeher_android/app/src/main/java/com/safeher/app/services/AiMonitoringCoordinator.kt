package com.safeher.app.services

import com.safeher.app.core.datastore.AiSettingsStore
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.AiAction
import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.domain.model.AiTriggerSource
import com.safeher.app.domain.model.SensorScores
import com.safeher.app.domain.repository.AiRepository
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.services.ai.AiDetectionLogger
import com.safeher.app.services.ai.AiFeatureFlags
import com.safeher.app.services.ai.AudioClipEncoder
import com.safeher.app.services.ai.AudioInferenceEngine
import com.safeher.app.services.ai.AudioHybridPipeline
import com.safeher.app.services.ai.AudioRiskAssessment
import com.safeher.app.services.ai.MovementInferenceEngine
import com.safeher.app.services.ai.PendingAudioDetection
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
    data class ShowEmergencyConfirmation(val detection: PendingAudioDetection) : AiCoordinatorEvent
}

@Singleton
class AiMonitoringCoordinator @Inject constructor(
    private val aiRepository: AiRepository,
    private val alertRepository: AlertRepository,
    private val alertSessionManager: AlertSessionManager,
    private val aiSettingsStore: AiSettingsStore,
    private val settingsStore: SettingsStore,
    private val audioHybridPipeline: AudioHybridPipeline,
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

    private val _isAppInForeground = MutableStateFlow(false)
    val isAppInForeground: StateFlow<Boolean> = _isAppInForeground.asStateFlow()

    private val _confidence = MutableStateFlow<AiConfidenceResult?>(null)
    val confidence: StateFlow<AiConfidenceResult?> = _confidence.asStateFlow()

    private val _riskAssessment = MutableStateFlow<AudioRiskAssessment?>(null)
    val riskAssessment: StateFlow<AudioRiskAssessment?> = _riskAssessment.asStateFlow()

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
    private var audioDetectionEnabled = true
    private var movementDetectionEnabled = true
    private var inferenceIntervalMs = INFERENCE_INTERVAL_MS
    private var helpImproveAiEnabled = false

    private var cooldownUntilMs = 0L
    private var pendingDetection: PendingAudioDetection? = null
    private var pendingConfidenceResult: AiConfidenceResult? = null
    private var pendingScores: SensorScores? = null

    fun startObserving() {
        if (started) return
        started = true
        _modelsAvailable.value = audioInferenceEngine.isAvailable

        applicationScope.scope.launch {
            aiSettingsStore.monitoringEnabled.collect { enabled ->
                if (enabled) startMonitoringInternal() else stopMonitoringInternal()
            }
        }

        applicationScope.scope.launch {
            aiSettingsStore.isIsolated.collect { isolated -> _isIsolated.value = isolated }
        }

        applicationScope.scope.launch {
            settingsStore.aiAudioDetectionEnabled.collect { enabled ->
                audioDetectionEnabled = enabled
                if (_isMonitoring.value) refreshMonitoringServices()
            }
        }

        applicationScope.scope.launch {
            settingsStore.aiMovementDetectionEnabled.collect { enabled ->
                movementDetectionEnabled = enabled
                if (_isMonitoring.value) refreshMonitoringServices()
            }
        }

        applicationScope.scope.launch {
            settingsStore.aiSensitivity.collect { sensitivity ->
                inferenceIntervalMs = sensitivity.toIntervalMs()
            }
        }

        applicationScope.scope.launch {
            settingsStore.aiHelpImproveEnabled.collect { enabled ->
                helpImproveAiEnabled = enabled
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
        applicationScope.scope.launch { aiSettingsStore.setMonitoringEnabled(false) }
    }

    fun refreshConfidence() {
        val scores = lastSensorScores ?: return
        if (!scores.hasAnyScore) return
        applicationScope.scope.launch { queryConfidence(scores, useSmoothedAudio = true) }
    }

    fun clearError() {
        _error.value = null
    }

    /**
     * User responded to the emergency confirmation dialog.
     * [confirmedEmergency] true → proceed with backend-recommended action.
     */
    fun onEmergencyConfirmation(confirmedEmergency: Boolean) {
        applicationScope.scope.launch {
            val detection = pendingDetection
            val confidenceResult = pendingConfidenceResult
            val scores = pendingScores
            pendingDetection = null
            pendingConfidenceResult = null
            pendingScores = null

            if (detection != null && helpImproveAiEnabled) {
                val label = if (confirmedEmergency) "emergency_confirmed" else "false_positive"
                aiRepository.queueDatasetSample(
                    audioWav = AudioClipEncoder.encodeWavMono16(detection.audioBuffer),
                    modelVersion = detection.modelVersion,
                    aiConfidence = detection.rollingAverage.toFloat(),
                    userConfirmation = confirmedEmergency,
                    label = label,
                    durationSeconds = detection.riskAssessment.durationSeconds.toFloat(),
                    featuresJson = buildFeaturesJson(detection),
                )
            }

            AiDetectionLogger.logUserConfirmation(confirmedEmergency, helpImproveAiEnabled && detection != null)

            enterCooldown()

            if (confirmedEmergency && confidenceResult != null && scores != null) {
                executeConfidenceAction(confidenceResult, scores)
            } else {
                audioHybridPipeline.reset()
                _riskAssessment.value = null
            }
        }
    }

    private suspend fun startMonitoringInternal() {
        if (_isMonitoring.value) return
        _isMonitoring.value = true
        refreshMonitoringServices()
        if (_isAppInForeground.value) startInferenceLoop()
    }

    private fun refreshMonitoringServices() {
        if (audioDetectionEnabled && _modelsAvailable.value) {
            audioMonitoringLauncher.startMonitoring()
        } else {
            audioMonitoringLauncher.stopMonitoring()
        }
        if (movementDetectionEnabled &&
            AiFeatureFlags.MOVEMENT_AI_ENABLED &&
            movementInferenceEngine.isAvailable
        ) {
            movementMonitorService.startMonitoring()
        } else {
            movementMonitorService.stopMonitoring()
        }
    }

    private fun stopMonitoringInternal() {
        if (!_isMonitoring.value) return
        _isMonitoring.value = false
        stopInferenceLoop()
        audioMonitoringLauncher.stopMonitoring()
        movementMonitorService.stopMonitoring()
        aiSensorState.reset()
        audioHybridPipeline.reset()
        _confidence.value = null
        _riskAssessment.value = null
        lastSensorScores = null
        pendingDetection = null
    }

    private fun startInferenceLoop() {
        if (!_modelsAvailable.value) return
        if (inferenceJob?.isActive == true) return
        inferenceJob = applicationScope.scope.launch {
            while (isActive && _isMonitoring.value && _isAppInForeground.value) {
                runInferenceCycle()
                delay(inferenceIntervalMs)
            }
        }
    }

    private fun stopInferenceLoop() {
        inferenceJob?.cancel()
        inferenceJob = null
    }

    private suspend fun runInferenceCycle() {
        if (System.currentTimeMillis() < cooldownUntilMs) return
        if (pendingDetection != null) return

        val audioBuffer = aiSensorState.latestAudioBuffer.value ?: return
        val accelWindow = aiSensorState.latestAccelerometerWindow.value

        var audioScore: Double? = null
        var movementScore: Double? = null
        var fallDetected = false
        var cycleResult: AudioHybridPipeline.CycleResult? = null

        if (audioDetectionEnabled) {
            cycleResult = audioHybridPipeline.process(audioBuffer, AUDIO_SAMPLE_RATE)
            audioScore = cycleResult?.rollingAverage
            cycleResult?.assessment?.let { _riskAssessment.value = it }
        }

        if (movementInferenceEngine.isAvailable &&
            AiFeatureFlags.MOVEMENT_AI_ENABLED &&
            movementDetectionEnabled &&
            accelWindow != null
        ) {
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
            enterCooldown()
            return
        }

        val assessment = cycleResult?.assessment ?: return
        if (!assessment.shouldQueryBackend) return

        queryConfidence(scores, useSmoothedAudio = true, pendingCycle = cycleResult)
    }

    private suspend fun queryConfidence(
        scores: SensorScores,
        useSmoothedAudio: Boolean,
        pendingCycle: AudioHybridPipeline.CycleResult? = null,
    ) {
        _isLoadingConfidence.value = true
        _error.value = null
        val audioForBackend = if (useSmoothedAudio) {
            scores.audioScore?.toFloat() ?: 0f
        } else {
            scores.audioScore?.toFloat() ?: 0f
        }
        val result = aiRepository.getConfidence(
            audioScore = audioForBackend,
            movementScore = scores.movementScore?.toFloat() ?: 0f,
            isNight = isNightHour(),
            isIsolated = _isIsolated.value,
        )
        _isLoadingConfidence.value = false
        result.fold(
            onSuccess = { confidenceResult ->
                _confidence.value = confidenceResult
                AiDetectionLogger.logBackendQuery(audioForBackend, confidenceResult.action.name)
                handleConfidenceAction(confidenceResult, scores, pendingCycle)
            },
            onFailure = { error -> _error.value = error.message },
        )
    }

    private suspend fun handleConfidenceAction(
        confidenceResult: AiConfidenceResult,
        scores: SensorScores,
        pendingCycle: AudioHybridPipeline.CycleResult? = null,
    ) {
        when (confidenceResult.action) {
            AiAction.FIRE_IMMEDIATELY, AiAction.CONFIRM_30S -> {
                val detection = pendingCycle?.let {
                    PendingAudioDetection(
                        rawConfidence = it.rawConfidence,
                        rollingAverage = it.rollingAverage,
                        riskAssessment = it.assessment,
                        audioBuffer = it.audioBuffer.copyOf(),
                    )
                } ?: pendingDetection
                if (detection != null) {
                    pendingDetection = detection
                    pendingConfidenceResult = confidenceResult
                    pendingScores = scores
                    _events.emit(AiCoordinatorEvent.ShowEmergencyConfirmation(detection))
                }
            }
            AiAction.SILENT_VIBRATION, AiAction.NOTHING -> Unit
        }
    }

    private suspend fun executeConfidenceAction(
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
            onFailure = { error -> _error.value = error.message },
        )
    }

    private fun enterCooldown() {
        val cooldownMs = audioHybridPipeline.detectionConfig.cooldownSeconds * 1_000L
        cooldownUntilMs = System.currentTimeMillis() + cooldownMs
        AiDetectionLogger.logCooldown(cooldownUntilMs)
        audioHybridPipeline.reset()
        _riskAssessment.value = null
    }

    private fun isNightHour(): Boolean {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return hour >= 22 || hour < 6
    }

    private fun buildFeaturesJson(detection: PendingAudioDetection): String {
        val f = detection.riskAssessment.features
        return """{"rms":${f.rmsEnergy},"peak":${f.peakAmplitude},"zcr":${f.zeroCrossingRate},"pitch_hz":${f.dominantFrequencyHz},"centroid_hz":${f.spectralCentroidHz},"rolling_avg":${detection.rollingAverage}}"""
    }

    companion object {
        private const val INFERENCE_INTERVAL_MS = 3_000L
        private const val AUDIO_SAMPLE_RATE = 16_000

        private fun com.safeher.app.domain.model.AiSensitivity.toIntervalMs(): Long = when (this) {
            com.safeher.app.domain.model.AiSensitivity.LOW -> 5_000L
            com.safeher.app.domain.model.AiSensitivity.MEDIUM -> 3_000L
            com.safeher.app.domain.model.AiSensitivity.HIGH -> 1_500L
        }
    }
}
