package com.safeher.app.services.ai

/** Snapshot retained for user confirmation. No PCM / WAV is kept or uploaded. */
data class PendingAudioDetection(
    val rawConfidence: Double,
    val rollingAverage: Double,
    val riskAssessment: AudioRiskAssessment,
    val modelVersion: String = AiModelVersion.AUDIO_DISTRESS,
    val timestampMs: Long = System.currentTimeMillis(),
    val signalType: String = "audio",
)
