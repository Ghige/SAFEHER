package com.safeher.app.services.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioRiskEvaluatorTest {

    private val config = AiDetectionConfig(
        confidenceThreshold = 75.0,
        minimumDurationSeconds = 5.0,
    )

    @Test
    fun highRisk_requiresMultipleSignalsAndDuration() {
        val features = AudioFrameFeatures(
            rmsEnergy = 0.2,
            peakAmplitude = 0.8,
            zeroCrossingRate = 0.1,
            dominantFrequencyHz = 400.0,
            spectralCentroidHz = 2500.0,
        )
        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = 88.0,
            rollingAverage = 87.0,
            durationSeconds = 6.0,
            features = features,
            baselineRms = 0.05,
            baselineCentroid = 1200.0,
            isSingleSpike = false,
        )
        assertEquals(AudioRiskLevel.HIGH, assessment.riskLevel)
        assertTrue(assessment.shouldQueryBackend)
    }

    @Test
    fun impulsiveNoise_downgradesShortDoorSlam() {
        val features = AudioFrameFeatures(
            rmsEnergy = 0.25,
            peakAmplitude = 0.9,
            zeroCrossingRate = 0.4,
            dominantFrequencyHz = 200.0,
            spectralCentroidHz = 1800.0,
        )
        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = 85.0,
            rollingAverage = 84.0,
            durationSeconds = 1.0,
            features = features,
            baselineRms = 0.05,
            baselineCentroid = 1200.0,
            isSingleSpike = false,
        )
        assertEquals(AudioRiskLevel.LOW, assessment.riskLevel)
        assertFalse(assessment.shouldQueryBackend)
    }

    @Test
    fun singleSpike_preventsSustainedConfidence() {
        val features = AudioFrameFeatures(
            rmsEnergy = 0.15,
            peakAmplitude = 0.7,
            zeroCrossingRate = 0.12,
            dominantFrequencyHz = 300.0,
            spectralCentroidHz = 2000.0,
        )
        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = 95.0,
            rollingAverage = 78.0,
            durationSeconds = 6.0,
            features = features,
            baselineRms = 0.05,
            baselineCentroid = 1200.0,
            isSingleSpike = true,
        )
        assertFalse(assessment.sustainedConfidence)
    }
}
