package com.safeher.app.services.ai

/**
 * On-device Safety Decision Engine mirror.
 * Values come from [DecisionContract] (shared with decision_contract.json).
 * Authoritative fusion remains on the backend; this guides local gating/UX.
 */
object SafetyDecisionEngine {

    enum class RiskLevel { LOW, MEDIUM, HIGH }

    data class AudioModelResult(
        val distressScore: Double = 0.0,
        val audioConfidence: Double = 0.0,
        val volumeScore: Double = 0.0,
    )

    data class SpeechModelResult(
        val phraseDetected: Boolean = false,
        val phraseScore: Double = 0.0,
        val language: String? = null,
        val phrase: String? = null,
    )

    data class MovementModelResult(
        val movementAnomalyScore: Double = 0.0,
        val fallDetected: Boolean = false,
    )

    data class SafetyDecision(
        val riskScore: Double,
        val riskLevel: RiskLevel,
        val reasonCodes: List<String>,
        val shouldConfirm: Boolean,
        val shouldTriggerSos: Boolean,
        val action: String = DecisionContract.ACTION_NOTHING,
        val state: String = DecisionContract.STATE_NORMAL,
        val confirmCountdownSeconds: Int = DecisionContract.CONFIRM_COUNTDOWN_SECONDS,
        val contractVersion: String = DecisionContract.CONTRACT_VERSION,
    )

    fun decide(
        audio: AudioModelResult = AudioModelResult(),
        speech: SpeechModelResult = SpeechModelResult(),
        movement: MovementModelResult = MovementModelResult(),
    ): SafetyDecision {
        if (movement.fallDetected) {
            return SafetyDecision(
                riskScore = 1.0,
                riskLevel = RiskLevel.HIGH,
                reasonCodes = listOf("FALL_DETECTED"),
                shouldConfirm = false,
                shouldTriggerSos = true,
                action = DecisionContract.ACTION_FIRE,
                state = DecisionContract.STATE_EMERGENCY,
            )
        }

        var distress = clamp01(audio.distressScore.takeIf { it > 0 } ?: audio.audioConfidence)
        if (distress > 1.0) distress = clamp01(distress / 100.0)
        var phrase = clamp01(speech.phraseScore)
        if (phrase > 1.0) phrase = clamp01(phrase / 100.0)
        var move = clamp01(movement.movementAnomalyScore)
        if (move > 1.0) move = clamp01(move / 100.0)
        var volume = clamp01(audio.volumeScore)
        if (volume > 1.0) volume = clamp01(volume / 100.0)

        val reasons = mutableListOf<String>()
        var score = 0.0

        if (distress >= DecisionContract.DISTRESS_MEDIUM) {
            score += DecisionContract.WEIGHT_DISTRESS * distress
            reasons += "DISTRESS_AUDIO"
        }
        if (phrase >= DecisionContract.PHRASE_MEDIUM) {
            score += DecisionContract.WEIGHT_PHRASE * phrase
            reasons += "EMERGENCY_PHRASE"
        }
        if (move >= DecisionContract.MOVE_MEDIUM) {
            score += DecisionContract.WEIGHT_MOVEMENT * move
            reasons += "ABNORMAL_MOVEMENT"
        }

        if (volume >= DecisionContract.VOLUME_LOUD && distress >= DecisionContract.DISTRESS_MEDIUM) {
            score += DecisionContract.WEIGHT_VOLUME * volume
            reasons += "VOLUME_FEATURE"
        } else if (
            volume >= DecisionContract.VOLUME_LOUD &&
            distress < DecisionContract.DISTRESS_MEDIUM &&
            phrase < DecisionContract.PHRASE_MEDIUM
        ) {
            reasons += "LOUD_WITHOUT_DISTRESS_SUPPRESSED"
        }

        val strong = listOf(
            distress >= DecisionContract.DISTRESS_HIGH,
            phrase >= DecisionContract.PHRASE_HIGH,
            move >= DecisionContract.MOVE_HIGH,
        ).count { it }
        if (strong >= 2) {
            score += DecisionContract.MULTI_STRONG_BONUS
            reasons += "MULTI_SIGNAL_CONFIRMATION"
        }

        val distressOrPhrase =
            distress >= DecisionContract.DISTRESS_MEDIUM || phrase >= DecisionContract.PHRASE_MEDIUM
        if (move >= DecisionContract.MOVE_MEDIUM && !distressOrPhrase) {
            score = minOf(score, DecisionContract.RISK_MEDIUM - 0.01)
            reasons += "MOVEMENT_ONLY_SUPPRESSED"
        }

        if (
            phrase >= DecisionContract.PHRASE_HIGH &&
            distress < DecisionContract.DISTRESS_MEDIUM &&
            move < DecisionContract.MOVE_MEDIUM
        ) {
            score = maxOf(score, DecisionContract.RISK_MEDIUM)
        }
        if (phrase >= DecisionContract.PHRASE_HIGH && distress >= DecisionContract.DISTRESS_MEDIUM) {
            score = maxOf(score, DecisionContract.RISK_HIGH)
        }
        if (distress >= DecisionContract.DISTRESS_HIGH && phrase < DecisionContract.PHRASE_MEDIUM) {
            score = maxOf(score, DecisionContract.RISK_HIGH * 0.95)
        }
        if (distress >= DecisionContract.DISTRESS_FLOOR_HIGH) {
            score = maxOf(score, DecisionContract.RISK_HIGH)
        } else if (distress >= DecisionContract.DISTRESS_FLOOR_MEDIUM) {
            score = maxOf(score, DecisionContract.RISK_MEDIUM)
        }

        if (
            volume >= DecisionContract.VOLUME_LOUD &&
            distress < DecisionContract.DISTRESS_MEDIUM &&
            phrase < DecisionContract.PHRASE_MEDIUM
        ) {
            score = minOf(score, DecisionContract.RISK_MEDIUM - 0.05)
        }

        score = clamp01(score)
        val (level, action, state) = when {
            score >= DecisionContract.RISK_HIGH ->
                Triple(RiskLevel.HIGH, DecisionContract.ACTION_FIRE, DecisionContract.STATE_EMERGENCY)
            score >= DecisionContract.RISK_MEDIUM ->
                Triple(RiskLevel.MEDIUM, DecisionContract.ACTION_CONFIRM, DecisionContract.STATE_SUSPICIOUS)
            score >= DecisionContract.RISK_SILENT ->
                Triple(RiskLevel.LOW, DecisionContract.ACTION_SILENT, DecisionContract.STATE_NORMAL)
            else ->
                Triple(RiskLevel.LOW, DecisionContract.ACTION_NOTHING, DecisionContract.STATE_NORMAL)
        }

        return SafetyDecision(
            riskScore = score,
            riskLevel = level,
            reasonCodes = reasons.distinct(),
            shouldConfirm = level == RiskLevel.MEDIUM || level == RiskLevel.HIGH,
            shouldTriggerSos = level == RiskLevel.HIGH,
            action = action,
            state = state,
        )
    }

    private fun clamp01(x: Double): Double = x.coerceIn(0.0, 1.0)
}
