package com.safeher.app.services.ai

/**
 * Tunable on-device gates for hybrid audio + multi-signal safety.
 * Phrase gates align with [DecisionContract]. Volume is a FEATURE only.
 */
data class AiDetectionConfig(
    /**
     * Score gate for a "hot" 1-second window (0–100). Configurable default, not a
     * production-final constant and not a DecisionContract value.
     */
    val confidenceThreshold: Double = 75.0,
    /** Minimum seconds of sustained elevated confidence (legacy rolling-window path). */
    val minimumDurationSeconds: Double = 5.0,
    /** UI popup cooldown after dismiss. Does not stop inference. */
    val cooldownSeconds: Long = 60L,
    /** Number of inference samples in the rolling window (~1 sample per 1 s hop). */
    val rollingWindowSize: Int = 8,
    /**
     * Score-history length for sustained-distress (about 5–7 s of 1 s hops).
     * Not the TFLite input length — the model still sees 1 second.
     */
    val evidenceHorizonSeconds: Double = 6.0,
    /** Consecutive 1 s scores >= [confidenceThreshold] required for consecutive-hot. */
    val consecutiveHotRequired: Int = 3,
    /** Enable consecutive-hot sustained logic. */
    val useConsecutiveHotLogic: Boolean = true,
    /** Enable N-of-M sustained logic (OR with consecutive-hot). */
    val allowNOfMLogic: Boolean = true,
    /** N in N-of-M: hot windows required inside [nOfMWindow]. */
    val nOfMHotCount: Int = 4,
    /** M in N-of-M: last M 1-second scores. */
    val nOfMWindow: Int = 6,
    /** Quiet gap before a new distress episode id is assigned. */
    val episodeQuietGapSeconds: Double = 8.0,
    /** Max confirm popups in [popupFrequencyPeriodSeconds]. UI only; does not stop scoring. */
    val maxPopupsPerPeriod: Int = 3,
    /** Window for [maxPopupsPerPeriod]. */
    val popupFrequencyPeriodSeconds: Long = 600L,
    /** Extra score (0–100) vs last shown popup to reopen eligibility for the same episode. */
    val escalationScoreMargin: Double = 10.0,
    /** RMS multiplier vs recent baseline to flag a volume spike (feature only). */
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
    /** Phrase score (0–1) — DecisionContract.PHRASE_MEDIUM. */
    val phraseScoreMedium: Double = DecisionContract.PHRASE_MEDIUM,
    /** Phrase score (0–1) — DecisionContract.PHRASE_HIGH. */
    val phraseScoreHigh: Double = DecisionContract.PHRASE_HIGH,
)
