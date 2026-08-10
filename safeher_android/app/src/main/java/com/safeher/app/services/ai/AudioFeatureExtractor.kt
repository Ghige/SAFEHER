package com.safeher.app.services.ai

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Extracts acoustic features from PCM samples for the hybrid distress pipeline.
 * Pure Kotlin — no synthetic scores; operates on real microphone data only.
 */
object AudioFeatureExtractor {

    private const val SAMPLE_RATE = 16_000

    fun extract(samples: ShortArray): AudioFrameFeatures {
        val normalized = FloatArray(samples.size) { i -> samples[i] / 32768f }
        val rms = computeRms(normalized)
        val peak = normalized.maxOf { abs(it.toDouble()) }
        val zcr = computeZeroCrossingRate(normalized)
        val pitch = estimateDominantFrequency(normalized)
        val centroid = estimateSpectralCentroid(normalized)
        return AudioFrameFeatures(
            rmsEnergy = rms,
            peakAmplitude = peak,
            zeroCrossingRate = zcr,
            dominantFrequencyHz = pitch,
            spectralCentroidHz = centroid,
        )
    }

    private fun computeRms(samples: FloatArray): Double {
        if (samples.isEmpty()) return 0.0
        var sumSq = 0.0
        for (sample in samples) {
            sumSq += sample * sample
        }
        return sqrt(sumSq / samples.size)
    }

    private fun computeZeroCrossingRate(samples: FloatArray): Double {
        if (samples.size < 2) return 0.0
        var crossings = 0
        for (i in 1 until samples.size) {
            if ((samples[i] >= 0) != (samples[i - 1] >= 0)) crossings++
        }
        return crossings.toDouble() / (samples.size - 1)
    }

    /**
     * Autocorrelation peak for fundamental frequency (pitch) estimation.
     */
    private fun estimateDominantFrequency(samples: FloatArray): Double {
        val maxLag = (SAMPLE_RATE / 80).coerceAtMost(samples.size / 2)
        val minLag = (SAMPLE_RATE / 800).coerceAtLeast(2)
        if (maxLag <= minLag) return 0.0

        var bestLag = minLag
        var bestCorr = 0.0
        for (lag in minLag..maxLag) {
            var corr = 0.0
            val limit = samples.size - lag
            for (i in 0 until limit) {
                corr += samples[i] * samples[i + lag]
            }
            if (corr > bestCorr) {
                bestCorr = corr
                bestLag = lag
            }
        }
        return if (bestCorr <= 0) 0.0 else SAMPLE_RATE.toDouble() / bestLag
    }

    /**
     * Band-weighted spectral centroid estimate via sparse Goertzel bins.
     */
    private fun estimateSpectralCentroid(samples: FloatArray): Double {
        val binFreqs = intArrayOf(200, 400, 800, 1200, 2000, 3000, 4000)
        var weightedSum = 0.0
        var totalPower = 0.0
        for (freq in binFreqs) {
            val power = goertzelPower(samples, freq)
            weightedSum += freq * power
            totalPower += power
        }
        return if (totalPower <= 1e-9) 0.0 else weightedSum / totalPower
    }

    private fun goertzelPower(samples: FloatArray, targetHz: Int): Double {
        val k = (0.5 + samples.size * targetHz.toDouble() / SAMPLE_RATE).toInt()
        val omega = 2.0 * PI * k / samples.size
        val coeff = 2.0 * cos(omega)
        var sPrev = 0.0
        var sPrev2 = 0.0
        for (sample in samples) {
            val s = sample + coeff * sPrev - sPrev2
            sPrev2 = sPrev
            sPrev = s
        }
        val real = sPrev - sPrev2 * cos(omega)
        val imag = sPrev2 * sin(omega)
        return real * real + imag * imag
    }
}
