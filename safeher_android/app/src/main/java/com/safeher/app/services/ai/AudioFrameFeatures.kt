package com.safeher.app.services.ai

/** Signal features extracted from a 1-second 16 kHz audio window. */
data class AudioFrameFeatures(
    val rmsEnergy: Double,
    val peakAmplitude: Double,
    val zeroCrossingRate: Double,
    val dominantFrequencyHz: Double,
    val spectralCentroidHz: Double,
)
