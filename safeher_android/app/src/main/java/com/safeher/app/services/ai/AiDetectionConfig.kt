package com.safeher.app.services.ai

/**
 * Tunable thresholds for the hybrid audio detection pipeline.
 * Values align with backend fusion tiers but gating happens on-device first.
 */
data class AiDetectionConfig(
    /** Rolling average must exceed this before backend is queried (0–100). */
    val confidenceThreshold: Double = 75.0,
    /** Minimum seconds of sustained elevated confidence. */
    val minimumDurationSeconds: Double = 5.0,
    /** Cooldown after a detection event before re-arming. */
    val cooldownSeconds: Long = 60L,
    /** Number of inference samples in the rolling window (~1 sample per cycle). */
    val rollingWindowSize: Int = 8,
    /** RMS multiplier vs recent baseline to flag a volume spike. */
    val volumeSpikeMultiplier: Double = 2.5,
    /** Absolute RMS floor for spike detection (normalized 0–1). */
    val absoluteVolumeSpikeRms: Double = 0.12,
    /** Hz change from baseline spectral centroid considered abnormal. */
    val frequencyChangeThresholdHz: Double = 800.0,
    /** Dominant frequency above this suggests scream-like content. */
    val screamFrequencyThresholdHz: Double = 350.0,
    /** ZCR above this with low duration suggests impulsive noise (door slam). */
    val impulsiveZcrThreshold: Double = 0.35,
    /** Max duration (seconds) for impulsive sounds — ignored as distress. */
    val impulsiveMaxDurationSeconds: Double = 1.5,
)
