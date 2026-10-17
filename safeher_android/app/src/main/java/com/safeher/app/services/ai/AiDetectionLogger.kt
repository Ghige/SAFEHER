package com.safeher.app.services.ai

import timber.log.Timber

/**
 * Structured diagnostics for hybrid inference.
 * Never logs raw PCM/audio bytes, precise GPS, full phone numbers, or full speech transcripts.
 */
object AiDetectionLogger {

    /** Stable Logcat tag for Stage 3A physical-device proof. Never includes PCM. */
    const val LIVE_TAG = "SAFEHER_AI"

    fun logFrame(
        rawConfidence: Double,
        rollingAverage: Double?,
        assessment: AudioRiskAssessment?,
        modelVersion: String,
    ) {
        Timber.d(
            "AI audio frame model=%s raw=%.1f rolling=%s risk=%s volSpike=%s freqAbn=%s dur=%.1fs impulsive=%s rms=%.4f zcr=%.3f pitch=%.0fHz centroid=%.0fHz",
            modelVersion,
            rawConfidence,
            rollingAverage?.let { "%.1f".format(it) } ?: "n/a",
            assessment?.riskLevel?.name ?: "n/a",
            assessment?.volumeSpike ?: false,
            assessment?.frequencyAbnormal ?: false,
            assessment?.durationSeconds ?: 0.0,
            assessment?.impulsiveNoise ?: false,
            assessment?.features?.rmsEnergy ?: 0.0,
            assessment?.features?.zeroCrossingRate ?: 0.0,
            assessment?.features?.dominantFrequencyHz ?: 0.0,
            assessment?.features?.spectralCentroidHz ?: 0.0,
        )
    }

    fun logInferenceTiming(component: String, latencyMs: Long, score: Double?) {
        Timber.d(
            "AI timing component=%s latencyMs=%d score=%s",
            component,
            latencyMs,
            score?.let { "%.1f".format(it) } ?: "null",
        )
    }

    fun logLocalDecision(decision: SafetyDecisionEngine.SafetyDecision?) {
        if (decision == null) return
        Timber.d(
            "AI local SDE contract=%s state=%s action=%s risk=%.3f reasons=%s confirmCountdown=%ds autoSos=%s",
            decision.contractVersion,
            decision.state,
            decision.action,
            decision.riskScore,
            decision.reasonCodes.joinToString(","),
            decision.confirmCountdownSeconds,
            AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
    }

    /** Stage 11: log length + finality only — no transcript text (PII). */
    fun logSpeechTranscript(text: String?, isFinal: Boolean) {
        val len = text?.length ?: 0
        Timber.d(
            "AI speech event final=%s transcript_len=%d autoSos=%s",
            isFinal,
            len,
            AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
    }

    fun logModelStatus(status: AiModelRuntimeStatus) {
        Timber.i(
            "AI models audio=%s speech=%s movement=%s contract=%s autoSos=%s | %s | %s | %s",
            status.audioAvailable,
            status.speechMode,
            status.movementAvailable,
            status.contractVersion,
            status.aiAutoSosEnabled,
            status.audioDetail,
            status.speechDetail,
            status.movementDetail,
        )
    }

    fun logMovementSkipped(reason: String) {
        Timber.d("AI movement inference skipped: %s", reason)
    }

    fun logBackendQuery(smoothedScore: Float, action: String?) {
        Timber.i(
            "AI backend /confidence smoothed=%.1f action=%s autoSos=%s",
            smoothedScore,
            action ?: "pending",
            AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
    }

    fun logUserConfirmation(confirmedEmergency: Boolean, uploadQueued: Boolean) {
        Timber.i(
            "AI user confirmation emergency=%s uploadQueued=%s autoSos=%s",
            confirmedEmergency,
            uploadQueued,
            AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
    }

    /** Stage 8/11 confirm audit (Timber). Avoid embedding phones/coords/transcripts in [detail]. */
    fun logConfirmAudit(
        event: String,
        sessionId: String?,
        action: String?,
        detail: String?,
    ) {
        Timber.i(
            "AI_CONFIRM_AUDIT event=%s session=%s action=%s autoSos=%s detail=%s",
            event,
            sessionId ?: "-",
            action ?: "-",
            AiFeatureFlags.AI_AUTO_SOS_ENABLED,
            sanitizeDetail(detail),
        )
    }

    fun logCooldown(untilMs: Long) {
        Timber.d("AI popup cooldown until=%d inferenceContinues=true", untilMs)
    }

    fun logAudioWindow(
        sequence: Long,
        timestampMs: Long,
        sampleCount: Int,
        sampleRateHz: Int,
    ) {
        val durationMs = if (sampleRateHz > 0) sampleCount * 1000L / sampleRateHz else 0L
        Timber.d(
            "AI audio window seq=%d ts=%d samples=%d rate=%d durationMs=%d",
            sequence,
            timestampMs,
            sampleCount,
            sampleRateHz,
            durationMs,
        )
    }

    fun logInferenceExecution(sequence: Long, score: Double?, latencyMs: Long?) {
        Timber.d(
            "AI inference seq=%d score=%s latencyMs=%s",
            sequence,
            score?.let { "%.1f".format(it) } ?: "null",
            latencyMs?.toString() ?: "n/a",
        )
    }

    fun logTemporalState(decision: TemporalDecision) {
        Timber.d(
            "AI temporal state=%s consecutiveHot=%d hot=%d/%d max=%.1f threshold=%.1f episode=%s reason=%s",
            decision.state.name,
            decision.consecutiveHot,
            decision.hotInWindow,
            decision.windowSize,
            decision.maxScoreInHorizon,
            decision.threshold,
            decision.episodeId?.toString() ?: "-",
            decision.reason,
        )
    }

    fun logPopupEligibility(result: PopupEligibilityResult) {
        Timber.i(
            "AI popup eligible=%s reason=%s episode=%s stronger=%s inferenceContinues=%s",
            result.eligible,
            result.suppressionReason ?: "eligible",
            result.episodeId?.toString() ?: "-",
            result.strongerEvent,
            result.inferenceContinues,
        )
    }

    fun logWindowSequenceGap(lastSequence: Long, currentSequence: Long, droppedCount: Long) {
        Timber.w(
            "AI audio window gap lastSeq=%d currentSeq=%d dropped=%d",
            lastSequence,
            currentSequence,
            droppedCount,
        )
    }

    fun logScoringContext(
        monitoringActive: Boolean,
        appInForeground: Boolean,
        microphoneFgsRunning: Boolean,
        scoringAllowed: Boolean,
    ) {
        Timber.d(
            "AI scoring monitoring=%s foreground=%s micFgs=%s allowed=%s",
            monitoringActive,
            appInForeground,
            microphoneFgsRunning,
            scoringAllowed,
        )
    }

    fun liveWindowCreated(
        sequence: Long,
        timestampMs: Long,
        sampleCount: Int,
        sampleRateHz: Int,
    ) {
        val durationMs = if (sampleRateHz > 0) sampleCount * 1000L / sampleRateHz else 0L
        Timber.tag(LIVE_TAG).i(
            "window_created seq=%d ts=%d samples=%d rate=%d durationMs=%d",
            sequence,
            timestampMs,
            sampleCount,
            sampleRateHz,
            durationMs,
        )
    }

    fun liveWindowPolled(
        sequence: Long?,
        queueEmpty: Boolean,
        pendingCount: Int,
    ) {
        if (queueEmpty) {
            Timber.tag(LIVE_TAG).i("window_poll empty pending=%d", pendingCount)
        } else {
            Timber.tag(LIVE_TAG).i(
                "window_poll received seq=%d pending=%d",
                sequence ?: -1L,
                pendingCount,
            )
        }
    }

    fun liveTfliteBefore(sequence: Long, sampleCount: Int) {
        Timber.tag(LIVE_TAG).i("tflite_before seq=%d samples=%d", sequence, sampleCount)
    }

    fun liveTfliteAfter(
        sequence: Long,
        score: Double?,
        latencyMs: Long?,
        error: String?,
    ) {
        if (score == null) {
            Timber.tag(LIVE_TAG).i(
                "tflite_after seq=%d score=null latencyMs=%s error=%s",
                sequence,
                latencyMs?.toString() ?: "n/a",
                sanitizeDetail(error),
            )
        } else {
            Timber.tag(LIVE_TAG).i(
                "tflite_after seq=%d score=%.1f latencyMs=%s",
                sequence,
                score,
                latencyMs?.toString() ?: "n/a",
            )
        }
    }

    fun liveTemporal(sequence: Long, score: Double, state: String) {
        Timber.tag(LIVE_TAG).i(
            "temporal seq=%d score=%.1f state=%s",
            sequence,
            score,
            state,
        )
    }

    fun liveAsrPause(sequence: Long, reason: String, pauseStartMs: Long) {
        Timber.tag(LIVE_TAG).i(
            "asr_pause seq=%d reason=%s ts=%d",
            sequence,
            reason,
            pauseStartMs,
        )
    }

    fun liveCaptureResume(resumeTs: Long, nextSequence: Long) {
        Timber.tag(LIVE_TAG).i(
            "capture_resume ts=%d nextSeq=%d",
            resumeTs,
            nextSequence,
        )
    }

    private fun sanitizeDetail(detail: String?): String {
        if (detail.isNullOrBlank()) return "-"
        // Drop obvious coordinate / phone-like substrings from free-form detail
        return detail
            .replace(Regex("""\+?\d[\d\s\-()]{7,}\d"""), "[PHONE]")
            .replace(Regex("""-?\d{1,3}\.\d{3,}"""), "[NUM]")
            .take(120)
    }
}
