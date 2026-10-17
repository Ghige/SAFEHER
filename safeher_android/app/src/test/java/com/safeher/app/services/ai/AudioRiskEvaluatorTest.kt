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
    fun highRisk_sustainedDistress_withoutRequiringVolumeSpike() {
        // Quiet-ish RMS but sustained model confidence — volume must NOT block HIGH
        val features = AudioFrameFeatures(
            rmsEnergy = 0.04,
            peakAmplitude = 0.2,
            zeroCrossingRate = 0.1,
            dominantFrequencyHz = 400.0,
            spectralCentroidHz = 1300.0,
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
            phraseScore = 0.0,
        )
        assertEquals(AudioRiskLevel.HIGH, assessment.riskLevel)
        assertTrue(assessment.shouldQueryBackend)
        assertFalse(assessment.volumeSpike)
    }

    @Test
    fun quietHelpMe_phrase_canReachMediumWithoutVolume() {
        val features = AudioFrameFeatures(
            rmsEnergy = 0.03,
            peakAmplitude = 0.15,
            zeroCrossingRate = 0.08,
            dominantFrequencyHz = 200.0,
            spectralCentroidHz = 1100.0,
        )
        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = 30.0,
            rollingAverage = 28.0,
            durationSeconds = 2.0,
            features = features,
            baselineRms = 0.05,
            baselineCentroid = 1200.0,
            isSingleSpike = false,
            phraseScore = 0.95,
        )
        assertEquals(AudioRiskLevel.MEDIUM, assessment.riskLevel)
        assertTrue(assessment.phraseDetected)
    }

    @Test
    fun loudOnly_withoutDistress_staysLow() {
        val features = AudioFrameFeatures(
            rmsEnergy = 0.25,
            peakAmplitude = 0.9,
            zeroCrossingRate = 0.12,
            dominantFrequencyHz = 200.0,
            spectralCentroidHz = 1800.0,
        )
        val assessment = AudioRiskEvaluator.evaluate(
            config = config,
            rawConfidence = 20.0,
            rollingAverage = 18.0,
            durationSeconds = 3.0,
            features = features,
            baselineRms = 0.05,
            baselineCentroid = 1200.0,
            isSingleSpike = false,
            phraseScore = 0.0,
        )
        assertEquals(AudioRiskLevel.LOW, assessment.riskLevel)
        assertFalse(assessment.shouldQueryBackend)
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
