package com.safeher.app.services.ai

/** Snapshot retained for user confirmation and optional dataset upload. */
data class PendingAudioDetection(
    val rawConfidence: Double,
    val rollingAverage: Double,
    val riskAssessment: AudioRiskAssessment,
    val audioBuffer: ShortArray,
    val modelVersion: String = AiModelVersion.AUDIO_DISTRESS,
    val timestampMs: Long = System.currentTimeMillis(),
)
