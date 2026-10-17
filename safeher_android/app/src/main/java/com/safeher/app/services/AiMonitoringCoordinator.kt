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
import com.safeher.app.services.ai.AiConfirmFirstPolicy
import com.safeher.app.services.ai.AiDetectionLogger
import com.safeher.app.services.ai.AiFeatureFlags
import com.safeher.app.services.ai.AiFeedbackClassifier
import com.safeher.app.services.ai.AiInferenceSnapshot
import com.safeher.app.services.ai.AiModelRuntimeStatus
import com.safeher.app.services.ai.AiModelAssets
import com.safeher.app.services.ai.AudioHybridPipeline
import com.safeher.app.services.ai.AudioInferenceEngine
import com.safeher.app.services.ai.AudioRiskAssessment
import com.safeher.app.services.ai.ContinuousInferencePolicy
import com.safeher.app.services.ai.DecisionContract
import com.safeher.app.services.ai.PopupEligibilityController
import com.safeher.app.services.ai.TemporalDecision
import com.safeher.app.services.ai.MissingMovementInferenceEngine
import com.safeher.app.services.ai.MovementInferenceEngine
import com.safeher.app.services.ai.PendingAudioDetection
import com.safeher.app.services.ai.SpeechAsrController
import com.safeher.app.services.ai.SpeechAudioCoexistencePolicy
import com.safeher.app.services.ai.SpeechPhraseInferenceEngine
import com.safeher.app.services.ai.SpeechTranscriptStore
import java.util.UUID
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.BufferOverflow
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
    data class ShowEmergencyConfirmation(
        val detection: PendingAudioDetection?,
        val promptKind: AiConfirmFirstPolicy.PromptKind,
        val recommendedAction: String,
        val countdownSeconds: Int,
        val reason: String,
    ) : AiCoordinatorEvent
    data class ConfirmSessionTick(val secondsRemaining: Int) : AiCoordinatorEvent
    data class ConfirmSessionEnded(val outcome: String, val userMessage: String) : AiCoordinatorEvent
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
    private val speechPhraseInferenceEngine: SpeechPhraseInferenceEngine,
    private val speechAsrController: SpeechAsrController,
    private val speechTranscriptStore: SpeechTranscriptStore,
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

    private val _modelStatus = MutableStateFlow(buildModelStatus())
    val modelStatus: StateFlow<AiModelRuntimeStatus> = _modelStatus.asStateFlow()

    private val _inferenceSnapshot = MutableStateFlow<AiInferenceSnapshot?>(null)
    val inferenceSnapshot: StateFlow<AiInferenceSnapshot?> = _inferenceSnapshot.asStateFlow()

    private val _isIsolated = MutableStateFlow(false)
    val isIsolated: StateFlow<Boolean> = _isIsolated.asStateFlow()

    private val _events = MutableSharedFlow<AiCoordinatorEvent>(
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
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

    private val popupEligibility = PopupEligibilityController(audioHybridPipeline.detectionConfig)
    private var lastProcessedWindowSequence = 0L
    private var pendingEpisodeId: Long? = null
    private var pendingPopupScore: Double = 0.0
    private var pendingDetection: PendingAudioDetection? = null
    private var pendingConfidenceResult: AiConfidenceResult? = null
    private var pendingScores: SensorScores? = null
    private var pendingRecommendedAction: String = DecisionContract.ACTION_CONFIRM
    private var confirmSessionId: String? = null
    private var confirmCountdownJob: Job? = null
    private var confirmResolved = false
    private var lastAsrInterleaveMs = 0L
    private var asrInterleaveInFlight = false

    private val _confirmSecondsRemaining = MutableStateFlow(0)
    val confirmSecondsRemaining: StateFlow<Int> = _confirmSecondsRemaining.asStateFlow()

    private val _confirmPromptKind = MutableStateFlow<AiConfirmFirstPolicy.PromptKind?>(null)
    val confirmPromptKind: StateFlow<AiConfirmFirstPolicy.PromptKind?> = _confirmPromptKind.asStateFlow()

    fun startObserving() {
        if (started) return
        started = true
        _modelsAvailable.value = audioInferenceEngine.isAvailable
        _modelStatus.value = buildModelStatus()
        AiDetectionLogger.logModelStatus(_modelStatus.value)

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
        val allowed = scoringAllowed()
        AiDetectionLogger.logScoringContext(
            monitoringActive = _isMonitoring.value,
            appInForeground = inForeground,
            microphoneFgsRunning = audioMonitoringLauncher.isRunning.value,
            scoringAllowed = allowed,
        )
        if (allowed) startInferenceLoop() else stopInferenceLoop()
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
     * User responded to the Stage-8 confirm-first prompt.
     * [confirmedEmergency] true → manual SOS countdown; false → CANCEL (no alert).
     */
    fun onEmergencyConfirmation(confirmedEmergency: Boolean) {
        applicationScope.scope.launch {
            resolveConfirmSession(
                userConfirmed = confirmedEmergency,
                timedOut = false,
            )
        }
    }

    /** Explicit cancel alias for UI. */
    fun onConfirmCancelled() {
        onEmergencyConfirmation(false)
    }

    /**
     * User tapped "I need help" on the first prompt. Stop the 30s auto-dismiss
     * so a second confirmation can be shown. Does not send SOS and does not
     * resolve the confirm session.
     */
    fun pauseConfirmTimeoutForSecondStep() {
        confirmCountdownJob?.cancel()
        confirmCountdownJob = null
        AiDetectionLogger.logConfirmAudit(
            event = "confirm_second_step",
            sessionId = confirmSessionId,
            action = pendingRecommendedAction,
            detail = "timeout_paused;awaiting_send_alert_confirm",
        )
    }

    private suspend fun startMonitoringInternal() {
        if (_isMonitoring.value) return
        _isMonitoring.value = true
        refreshMonitoringServices()
        if (scoringAllowed()) startInferenceLoop()
    }

    private fun refreshMonitoringServices() {
        val useAudioCapture = audioDetectionEnabled && _modelsAvailable.value
        if (useAudioCapture) {
            // AudioRecord owns the mic — ASR cannot run concurrently.
            speechAsrController.stop()
            audioMonitoringLauncher.startMonitoring()
        } else {
            audioMonitoringLauncher.stopMonitoring()
            if (_isMonitoring.value) {
                speechAsrController.start()
            } else {
                speechAsrController.stop()
            }
        }

        // IMU levels for debug/UI; model scores only if TFLite engine available.
        if (movementDetectionEnabled && _isMonitoring.value) {
            movementMonitorService.startMonitoring()
        } else {
            movementMonitorService.stopMonitoring()
        }
        _modelStatus.value = buildModelStatus()
    }

    private fun stopMonitoringInternal() {
        if (!_isMonitoring.value) return
        _isMonitoring.value = false
        stopInferenceLoop()
        speechAsrController.stop()
        audioMonitoringLauncher.stopMonitoring()
        movementMonitorService.stopMonitoring()
        aiSensorState.reset()
        audioHybridPipeline.reset()
        speechTranscriptStore.clear()
        _confidence.value = null
        _riskAssessment.value = null
        _inferenceSnapshot.value = null
        lastSensorScores = null
        pendingDetection = null
        pendingEpisodeId = null
        pendingPopupScore = 0.0
        lastProcessedWindowSequence = 0L
        popupEligibility.reset()
        _modelStatus.value = buildModelStatus()
    }

    private fun startInferenceLoop() {
        // Audio TFLite path requires model; speech-only path runs when audio detection is off.
        if (!_modelsAvailable.value && audioDetectionEnabled) return
        if (inferenceJob?.isActive == true) return
        inferenceJob = applicationScope.scope.launch {
            AiDetectionLogger.logScoringContext(
                monitoringActive = _isMonitoring.value,
                appInForeground = _isAppInForeground.value,
                microphoneFgsRunning = audioMonitoringLauncher.isRunning.value,
                scoringAllowed = true,
            )
            while (isActive && scoringAllowed()) {
                runInferenceCycle()
                // Poll faster than 1 s so completed windows are scored. Sensitivity
                // interval is not allowed to skip hops.
                check(inferenceIntervalMs > 0L)
                delay(WINDOW_POLL_MS)
            }
        }
    }

    private fun scoringAllowed(): Boolean = ContinuousInferencePolicy.shouldScore(
        monitoringActive = _isMonitoring.value,
        appInForeground = _isAppInForeground.value,
        microphoneFgsRunning = audioMonitoringLauncher.isRunning.value,
    )

    private suspend fun maybeRunAsrInterleave(localState: String?) {
        if (!AiFeatureFlags.SPEECH_ASR_INTERLEAVE_ENABLED) return
        if (!audioDetectionEnabled || !_modelsAvailable.value) return
        if (!_isMonitoring.value || !_isAppInForeground.value) return
        if (SpeechAudioCoexistencePolicy.shouldDeferAsrForLocalState(localState)) return
        if (asrInterleaveInFlight) return
        val now = System.currentTimeMillis()
        if (now - lastAsrInterleaveMs < SpeechAudioCoexistencePolicy.INTERLEAVE_PERIOD_MS) return
        if (!speechAsrController.isAvailable) return

        asrInterleaveInFlight = true
        lastAsrInterleaveMs = now
        try {
            AiDetectionLogger.liveAsrPause(
                sequence = lastProcessedWindowSequence,
                reason = "asr_interleave",
                pauseStartMs = now,
            )
            AiDetectionLogger.logSpeechTranscript(
                "ASR_INTERLEAVE_START policy=${SpeechAudioCoexistencePolicy.STRATEGY_SUMMARY}",
                isFinal = false,
            )
            audioMonitoringLauncher.pauseMicCapture()
            delay(150)
            val transcript = speechAsrController.runOneShot(SpeechAudioCoexistencePolicy.ASR_SLOT_MS)
            if (!transcript.isNullOrBlank()) {
                // Re-run catalog against fresh transcript next cycle via SpeechTranscriptStore
                AiDetectionLogger.logSpeechTranscript(transcript, isFinal = true)
            }
        } finally {
            audioMonitoringLauncher.resumeMicCapture()
            asrInterleaveInFlight = false
        }
    }

    private fun buildModelStatus(): AiModelRuntimeStatus {
        val movementDetail = (movementInferenceEngine as? MissingMovementInferenceEngine)?.unavailableReason
            ?: if (movementInferenceEngine.isAvailable) {
                "Movement TFLite available"
            } else {
                AiModelAssets.MOVEMENT_UNAVAILABLE_REASON
            }
        return AiModelRuntimeStatus(
            audioAvailable = audioInferenceEngine.isAvailable,
            audioDetail = if (audioInferenceEngine.isAvailable) {
                "Loaded ${AiModelAssets.AUDIO_MODEL}"
            } else {
                audioInferenceEngine.lastError ?: "Audio TFLite not loaded"
            },
            speechMode = speechPhraseInferenceEngine.mode,
            speechDetail = speechPhraseInferenceEngine.detail,
            movementAvailable = movementInferenceEngine.isAvailable,
            movementDetail = movementDetail,
            contractVersion = DecisionContract.CONTRACT_VERSION,
            aiAutoSosEnabled = AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
    }

    private fun stopInferenceLoop() {
        inferenceJob?.cancel()
        inferenceJob = null
    }

    private suspend fun runInferenceCycle() {
        // Popup cooldown / visible popup / frequency never stop scoring.
        val accelWindow = aiSensorState.latestAccelerometerWindow.value

        var audioScore: Double? = null
        var movementScore: Double? = null
        var fallDetected = false
        var cycleResult: AudioHybridPipeline.CycleResult? = null
        var movementScore01: Double? = null

        if (movementInferenceEngine.isAvailable &&
            AiFeatureFlags.MOVEMENT_AI_ENABLED &&
            movementDetectionEnabled &&
            accelWindow != null
        ) {
            movementInferenceEngine.inferMovement(accelWindow)?.let { result ->
                movementScore = result.movementScore
                movementScore01 = result.movementScore / 100.0
                fallDetected = result.fallDetected
            }
        } else if (movementDetectionEnabled && accelWindow != null) {
            val reason = (movementInferenceEngine as? MissingMovementInferenceEngine)?.unavailableReason
                ?: AiModelAssets.MOVEMENT_UNAVAILABLE_REASON
            AiDetectionLogger.logMovementSkipped(reason)
        }

        val audioWindow = if (audioDetectionEnabled) {
            aiSensorState.pollCompletedWindow()
        } else {
            null
        }
        if (audioDetectionEnabled) {
            AiDetectionLogger.liveWindowPolled(
                sequence = audioWindow?.sequence,
                queueEmpty = audioWindow == null,
                pendingCount = aiSensorState.pendingCompletedWindowCount(),
            )
        }
        if (audioWindow != null) {
            if (lastProcessedWindowSequence > 0L &&
                audioWindow.sequence > lastProcessedWindowSequence + 1L
            ) {
                AiDetectionLogger.logWindowSequenceGap(
                    lastSequence = lastProcessedWindowSequence,
                    currentSequence = audioWindow.sequence,
                    droppedCount = aiSensorState.droppedCompletedWindowCount(),
                )
            }
            lastProcessedWindowSequence = audioWindow.sequence
            val sampleRate = if (audioWindow.sampleRateHz == AUDIO_SAMPLE_RATE) {
                audioWindow.sampleRateHz
            } else {
                AUDIO_SAMPLE_RATE
            }
            cycleResult = audioHybridPipeline.process(
                audioBuffer = audioWindow.samples,
                sampleRate = sampleRate,
                movementScore0to1 = movementScore01,
                fallDetected = fallDetected,
                windowSequence = audioWindow.sequence,
                windowTimestampMs = audioWindow.timestampMs,
            )
            audioScore = cycleResult?.rollingAverage
            cycleResult?.assessment?.let { _riskAssessment.value = it }
        } else if (audioDetectionEnabled) {
            // No new completed 1 s hop — do not re-score a stale buffer.
            return
        } else if (!audioDetectionEnabled) {
            // Speech-only / ASR path: phrase → local SDE without inventing audio scores.
            val phrase = speechPhraseInferenceEngine.inferFromLatestTranscript()
            if (phrase.phraseDetected) {
                val decision = com.safeher.app.services.ai.SafetyDecisionEngine.decide(
                    speech = com.safeher.app.services.ai.SafetyDecisionEngine.SpeechModelResult(
                        phraseDetected = true,
                        phraseScore = phrase.phraseScore,
                        language = phrase.language,
                        phrase = phrase.phrase,
                    ),
                    movement = com.safeher.app.services.ai.SafetyDecisionEngine.MovementModelResult(
                        movementAnomalyScore = movementScore01 ?: 0.0,
                        fallDetected = fallDetected,
                    ),
                )
                val phraseEligibility = evaluatePopupEligibility(
                    temporal = null,
                    currentScore = 0.0,
                    phraseConfirm = decision.shouldConfirm || decision.shouldTriggerSos,
                    fallConfirm = fallDetected,
                )
                _inferenceSnapshot.value = AiInferenceSnapshot(
                    phraseScore0to1 = phrase.phraseScore,
                    detectedPhrase = phrase.phrase,
                    movementScore0to100 = movementScore,
                    fallDetected = fallDetected,
                    localState = decision.state,
                    localAction = decision.action,
                    movementModelAvailable = movementInferenceEngine.isAvailable,
                    speechMode = speechPhraseInferenceEngine.mode,
                    popupEligible = phraseEligibility.eligible,
                    popupSuppressionReason = phraseEligibility.suppressionReason,
                )
                if ((decision.shouldConfirm || decision.shouldTriggerSos) && phraseEligibility.eligible) {
                    val scores = SensorScores(
                        audioScore = null,
                        movementScore = movementScore,
                        fallDetected = fallDetected,
                    )
                    lastSensorScores = scores
                    queryConfidence(
                        scores = scores,
                        useSmoothedAudio = true,
                        pendingCycle = null,
                        phraseScoreOverride = phrase.phraseScore,
                        detectedPhrase = phrase.phrase,
                        phraseLanguage = phrase.language,
                    )
                }
                return
            }
        }

        val scores = SensorScores(
            audioScore = audioScore,
            movementScore = movementScore,
            fallDetected = fallDetected,
        )

        val localDecision = cycleResult?.safetyDecision
        val phraseConfirm = (cycleResult?.phraseScore ?: 0.0) >=
            audioHybridPipeline.detectionConfig.phraseScoreMedium &&
            (localDecision?.shouldConfirm == true || localDecision?.shouldTriggerSos == true)
        val eligibility = evaluatePopupEligibility(
            temporal = cycleResult?.temporalDecision,
            currentScore = cycleResult?.rawConfidence ?: audioScore ?: 0.0,
            phraseConfirm = phraseConfirm,
            fallConfirm = fallDetected,
        )

        _inferenceSnapshot.value = AiInferenceSnapshot(
            audioLatencyMs = cycleResult?.audioLatencyMs ?: audioInferenceEngine.lastLatencyMs,
            pipelineLatencyMs = cycleResult?.pipelineLatencyMs,
            audioScore0to100 = audioScore,
            phraseScore0to1 = cycleResult?.phraseScore,
            detectedPhrase = cycleResult?.detectedPhrase,
            movementScore0to100 = movementScore,
            fallDetected = fallDetected,
            localState = cycleResult?.safetyDecision?.state,
            localAction = cycleResult?.safetyDecision?.action,
            lastError = audioInferenceEngine.lastError,
            movementModelAvailable = movementInferenceEngine.isAvailable,
            speechMode = speechPhraseInferenceEngine.mode,
            windowSequence = cycleResult?.windowSequence,
            windowTimestampMs = cycleResult?.windowTimestampMs,
            temporalState = cycleResult?.temporalDecision?.state?.name,
            popupEligible = eligibility.eligible,
            popupSuppressionReason = eligibility.suppressionReason,
        )

        // Duty-cycled ASR while continuous audio is primary (NORMAL only).
        maybeRunAsrInterleave(cycleResult?.safetyDecision?.state)

        if (!scores.hasAnyScore) return

        lastSensorScores = scores
        lastTriggerSource = when {
            fallDetected -> AiTriggerSource.MOVEMENT
            (audioScore ?: 0.0) >= (movementScore ?: 0.0) -> AiTriggerSource.AUDIO
            else -> AiTriggerSource.MOVEMENT
        }

        if (fallDetected && movementScore != null) {
            // Stage 8 confirm-first: fall NEVER silent-fires. Route through confirm UI.
            check(!DecisionContract.FALL_BYPASSES_CONFIRM_UI) {
                "Contract forbids fall confirm bypass"
            }
            if (eligibility.eligible) {
                queryConfidence(
                    scores,
                    useSmoothedAudio = true,
                    pendingCycle = cycleResult,
                    fallDetected = true,
                )
            }
            return
        }

        if (!eligibility.eligible) return

        queryConfidence(scores, useSmoothedAudio = true, pendingCycle = cycleResult)
    }

    private fun evaluatePopupEligibility(
        temporal: TemporalDecision?,
        currentScore: Double,
        phraseConfirm: Boolean,
        fallConfirm: Boolean,
    ): com.safeher.app.services.ai.PopupEligibilityResult {
        val config = audioHybridPipeline.detectionConfig
        val result = popupEligibility.evaluate(
            nowMs = System.currentTimeMillis(),
            temporal = temporal ?: TemporalDecision.none(
                threshold = config.confidenceThreshold,
                horizonSeconds = config.evidenceHorizonSeconds,
            ),
            currentScore = currentScore,
            popupVisibleOverride = confirmCountdownJob?.isActive == true ||
                popupEligibility.isPopupVisible,
            phraseConfirm = phraseConfirm,
            fallConfirm = fallConfirm,
        )
        AiDetectionLogger.logPopupEligibility(result)
        return result
    }

    private suspend fun queryConfidence(
        scores: SensorScores,
        useSmoothedAudio: Boolean,
        pendingCycle: AudioHybridPipeline.CycleResult? = null,
        phraseScoreOverride: Double? = null,
        detectedPhrase: String? = null,
        phraseLanguage: String? = null,
        fallDetected: Boolean = false,
    ) {
        _isLoadingConfidence.value = true
        _error.value = null
        val audioForBackend = if (useSmoothedAudio) {
            scores.audioScore?.toFloat() ?: 0f
        } else {
            scores.audioScore?.toFloat() ?: 0f
        }
        val phraseScore100 = (
            (phraseScoreOverride ?: pendingCycle?.phraseScore ?: 0.0) * 100.0
            ).toFloat()
        val volumeScore100 = (
            (pendingCycle?.assessment?.features?.rmsEnergy ?: 0.0) / 0.25 * 100.0
            ).coerceIn(0.0, 100.0).toFloat()
        val result = aiRepository.getConfidence(
            audioScore = audioForBackend,
            movementScore = scores.movementScore?.toFloat() ?: 0f,
            isNight = isNightHour(),
            isIsolated = _isIsolated.value,
            phraseScore = phraseScore100,
            volumeScore = volumeScore100,
            detectedPhrase = detectedPhrase ?: pendingCycle?.detectedPhrase,
            phraseLanguage = phraseLanguage ?: pendingCycle?.phraseLanguage,
            fallDetected = fallDetected || scores.fallDetected,
        )
        _isLoadingConfidence.value = false
        result.fold(
            onSuccess = { confidenceResult ->
                _confidence.value = confidenceResult
                AiDetectionLogger.logBackendQuery(audioForBackend, confidenceResult.action.name)
                handleConfidenceAction(confidenceResult, scores, pendingCycle)
            },
            onFailure = { error ->
                // Offline / API failure: still confirm-first from local SDE if available.
                val local = pendingCycle?.safetyDecision
                if (local != null && (local.shouldConfirm || local.shouldTriggerSos)) {
                    val synthetic = AiConfidenceResult(
                        totalScore = local.riskScore * 100.0,
                        action = when (local.action) {
                            DecisionContract.ACTION_FIRE -> AiAction.FIRE_IMMEDIATELY
                            DecisionContract.ACTION_CONFIRM -> AiAction.CONFIRM_30S
                            DecisionContract.ACTION_SILENT -> AiAction.SILENT_VIBRATION
                            else -> AiAction.NOTHING
                        },
                        activateGpsStream = local.shouldConfirm || local.shouldTriggerSos,
                        audioScore = scores.audioScore ?: 0.0,
                        movementScore = scores.movementScore ?: 0.0,
                        heartRateSpike = false,
                        isNight = isNightHour(),
                        isIsolated = _isIsolated.value,
                    )
                    AiDetectionLogger.logConfirmAudit(
                        event = "confidence_fallback_local_sde",
                        sessionId = confirmSessionId,
                        action = local.action,
                        detail = error.message ?: "backend_unavailable",
                    )
                    handleConfidenceAction(synthetic, scores, pendingCycle)
                } else {
                    _error.value = error.message
                }
            },
        )
    }

    private suspend fun handleConfidenceAction(
        confidenceResult: AiConfidenceResult,
        scores: SensorScores,
        pendingCycle: AudioHybridPipeline.CycleResult? = null,
    ) {
        when (confidenceResult.action) {
            AiAction.FIRE_IMMEDIATELY, AiAction.CONFIRM_30S -> {
                if (confirmCountdownJob?.isActive == true) {
                    AiDetectionLogger.logConfirmAudit(
                        event = "confirm_duplicate_suppressed",
                        sessionId = confirmSessionId,
                        action = confidenceResult.action.name,
                        detail = "session_already_active",
                    )
                    return
                }
                val detection = pendingCycle?.let {
                    PendingAudioDetection(
                        rawConfidence = it.rawConfidence,
                        rollingAverage = it.rollingAverage,
                        riskAssessment = it.assessment,
                    )
                } ?: pendingDetection
                pendingDetection = detection
                pendingConfidenceResult = confidenceResult
                pendingScores = scores
                pendingEpisodeId = pendingCycle?.temporalDecision?.episodeId
                pendingPopupScore = pendingCycle?.rawConfidence ?: confidenceResult.totalScore
                pendingRecommendedAction = when (confidenceResult.action) {
                    AiAction.FIRE_IMMEDIATELY -> DecisionContract.ACTION_FIRE
                    else -> DecisionContract.ACTION_CONFIRM
                }
                startConfirmSession(
                    detection = detection,
                    recommendedAction = pendingRecommendedAction,
                    reason = "sde_action=${confidenceResult.action.name};score=${confidenceResult.totalScore}",
                )
            }
            AiAction.SILENT_VIBRATION, AiAction.NOTHING -> Unit
        }
    }

    private suspend fun startConfirmSession(
        detection: PendingAudioDetection?,
        recommendedAction: String,
        reason: String,
    ) {
        if (alertSessionManager.activeAlert.value?.isOngoing == true) {
            AiDetectionLogger.logConfirmAudit(
                event = "confirm_suppressed_active_sos",
                sessionId = confirmSessionId,
                action = recommendedAction,
                detail = reason,
            )
            return
        }
        confirmCountdownJob?.cancel()
        confirmResolved = false
        val sessionId = UUID.randomUUID().toString()
        confirmSessionId = sessionId
        val seconds = AiConfirmFirstPolicy.countdownSeconds()
        val kind = AiConfirmFirstPolicy.promptKind(recommendedAction)
        _confirmPromptKind.value = kind
        _confirmSecondsRemaining.value = seconds

        AiDetectionLogger.logConfirmAudit(
            event = "confirm_prompt_shown",
            sessionId = sessionId,
            action = recommendedAction,
            detail = "kind=$kind;countdown=${seconds}s;$reason;autoSos=${AiFeatureFlags.AI_AUTO_SOS_ENABLED}",
        )

        popupEligibility.onPopupShown(
            episodeId = pendingEpisodeId,
            score = pendingPopupScore,
            nowMs = System.currentTimeMillis(),
        )

        _events.emit(
            AiCoordinatorEvent.ShowEmergencyConfirmation(
                detection = detection,
                promptKind = kind,
                recommendedAction = recommendedAction,
                countdownSeconds = seconds,
                reason = reason,
            ),
        )

        confirmCountdownJob = applicationScope.scope.launch {
            for (remaining in seconds downTo 1) {
                if (!isActive || confirmResolved) return@launch
                _confirmSecondsRemaining.value = remaining
                _events.emit(AiCoordinatorEvent.ConfirmSessionTick(remaining))
                delay(1_000L)
            }
            if (!confirmResolved) {
                resolveConfirmSession(userConfirmed = null, timedOut = true)
            }
        }
    }

    private suspend fun resolveConfirmSession(
        userConfirmed: Boolean?,
        timedOut: Boolean,
    ) {
        if (confirmResolved) return
        confirmResolved = true
        confirmCountdownJob?.cancel()
        confirmCountdownJob = null
        _confirmSecondsRemaining.value = 0
        _confirmPromptKind.value = null

        val detection = pendingDetection
        val confidenceResult = pendingConfidenceResult
        val scores = pendingScores
        val action = pendingRecommendedAction
        val sessionId = confirmSessionId
        pendingDetection = null
        pendingConfidenceResult = null
        pendingScores = null
        confirmSessionId = null
        pendingEpisodeId = null
        pendingPopupScore = 0.0

        if (detection != null && helpImproveAiEnabled) {
            val eventId = UUID.randomUUID().toString()
            aiRepository.submitFeedback(
                eventId = eventId,
                sessionId = sessionId ?: eventId,
                modelVersion = detection.modelVersion,
                signalType = detection.signalType,
                predictionState = AiFeedbackClassifier.predictionState(action),
                confidence = detection.rollingAverage,
                userFeedback = AiFeedbackClassifier.userFeedback(userConfirmed, timedOut),
                outcome = AiFeedbackClassifier.outcome(userConfirmed),
                consentGranted = true,
                consentVersion = AiFeedbackClassifier.CONSENT_VERSION,
                featuresJson = buildFeaturesJson(detection),
            )
        }

        val outcome = AiConfirmFirstPolicy.resolve(
            userConfirmed = userConfirmed,
            timedOut = timedOut,
            recommendedAction = action,
            autoSosEnabled = AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )

        AiDetectionLogger.logUserConfirmation(userConfirmed == true, helpImproveAiEnabled && detection != null)
        AiDetectionLogger.logConfirmAudit(
            event = "confirm_resolved",
            sessionId = sessionId,
            action = action,
            detail = "outcome=$outcome;userConfirmed=$userConfirmed;timedOut=$timedOut;" +
                "createsAlert=${AiConfirmFirstPolicy.createsAlert(outcome)};" +
                "autoSos=${AiFeatureFlags.AI_AUTO_SOS_ENABLED}",
        )

        enterPopupCooldown()

        val message = when (outcome) {
            AiConfirmFirstPolicy.Outcome.CANCELLED_NO_ALERT ->
                "Cancelled — no alert was sent."
            AiConfirmFirstPolicy.Outcome.NO_RESPONSE_DISMISS_SAFE,
            AiConfirmFirstPolicy.Outcome.NO_RESPONSE_BLOCKED_NO_ALERT,
            ->
                "No response — no alert was sent (AI auto-SOS is off)."
            AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_MANUAL_SOS,
            AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_AUTO_BLOCKED,
            ->
                "Opening manual SOS countdown. AI will not auto-send alerts."
        }
        _events.emit(AiCoordinatorEvent.ConfirmSessionEnded(outcome.name, message))

        if (AiConfirmFirstPolicy.opensManualSosCountdown(outcome)) {
            // Confirm-first: user-controlled manual SOS only. Never call AI SOS APIs here
            // while AI_AUTO_SOS_ENABLED is false (and Stage 8 keeps that false).
            check(!AiFeatureFlags.AI_AUTO_SOS_ENABLED || outcome == AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_AUTO_BLOCKED ||
                outcome == AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_MANUAL_SOS) {
                "Unexpected auto SOS state"
            }
            if (!AiFeatureFlags.AI_AUTO_SOS_ENABLED) {
                _events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            } else if (confidenceResult != null && scores != null) {
                // Out of Stage 8 product scope — still prefer manual path for safety.
                _events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            }
        }
        // Do not reset score history because a popup was shown or dismissed.
    }

    private suspend fun executeConfidenceAction(
        confidenceResult: AiConfidenceResult,
        scores: SensorScores,
    ) {
        when (confidenceResult.action) {
            AiAction.FIRE_IMMEDIATELY -> {
                if (!AiFeatureFlags.AI_AUTO_SOS_ENABLED) {
                    AiDetectionLogger.logConfirmAudit(
                        event = "ai_auto_sos_blocked",
                        sessionId = null,
                        action = DecisionContract.ACTION_FIRE,
                        detail = "AI_AUTO_SOS_ENABLED=false",
                    )
                    _error.value =
                        "Automatic AI SOS is disabled. Use the manual SOS button if you need help."
                    return
                }
                when (lastTriggerSource) {
                    AiTriggerSource.AUDIO -> handleAudioSos(scores)
                    AiTriggerSource.MOVEMENT -> handleMovementSos(scores)
                }
            }
            AiAction.CONFIRM_30S -> _events.emit(AiCoordinatorEvent.NavigateToSosCountdown)
            AiAction.SILENT_VIBRATION, AiAction.NOTHING -> Unit
        }
    }

    private suspend fun handleAudioSos(scores: SensorScores) {
        if (!AiFeatureFlags.AI_AUTO_SOS_ENABLED) {
            _error.value =
                "Automatic AI SOS is disabled. Use the manual SOS button if you need help."
            return
        }
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
        if (!AiFeatureFlags.AI_AUTO_SOS_ENABLED) {
            _error.value =
                "Automatic AI SOS is disabled. Use the manual SOS button if you need help."
            return
        }
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

    private fun enterPopupCooldown() {
        val now = System.currentTimeMillis()
        popupEligibility.onPopupDismissed(now)
        val cooldownMs = audioHybridPipeline.detectionConfig.cooldownSeconds * 1_000L
        AiDetectionLogger.logCooldown(now + cooldownMs)
        // Score history and TFLite scoring continue during UI cooldown.
    }

    private fun isNightHour(): Boolean {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return hour >= 22 || hour < 6
    }

    private fun buildFeaturesJson(detection: PendingAudioDetection): String {
        val f = detection.riskAssessment.features
        return """{"rms":${f.rmsEnergy},"peak":${f.peakAmplitude},"zcr":${f.zeroCrossingRate},"pitch_hz":${f.dominantFrequencyHz},"centroid_hz":${f.spectralCentroidHz},"rolling_avg":${detection.rollingAverage},"duration_seconds":${detection.riskAssessment.durationSeconds}}"""
    }

    companion object {
        private const val INFERENCE_INTERVAL_MS = 3_000L
        private const val WINDOW_POLL_MS = 200L
        private const val AUDIO_SAMPLE_RATE = 16_000

        private fun com.safeher.app.domain.model.AiSensitivity.toIntervalMs(): Long = when (this) {
            com.safeher.app.domain.model.AiSensitivity.LOW -> 5_000L
            com.safeher.app.domain.model.AiSensitivity.MEDIUM -> 3_000L
            com.safeher.app.domain.model.AiSensitivity.HIGH -> 1_500L
        }
    }
}
