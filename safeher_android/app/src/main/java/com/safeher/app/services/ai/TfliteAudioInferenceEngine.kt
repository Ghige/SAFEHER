package com.safeher.app.services.ai

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import org.tensorflow.lite.Interpreter
import timber.log.Timber
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.abs

@Singleton
class TfliteAudioInferenceEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) : AudioInferenceEngine {

    private val interpreter: Interpreter?

    override val isAvailable: Boolean

    init {
        interpreter = try {
            val modelBuffer = loadModelFile(AiModelAssets.AUDIO_MODEL)
            Interpreter(modelBuffer).also {
                Timber.i("Loaded audio TFLite model: ${AiModelAssets.AUDIO_MODEL}")
            }
        } catch (e: Exception) {
            Timber.e(e, "Failed to load audio TFLite model")
            null
        }
        isAvailable = interpreter != null
    }

    override suspend fun inferDistressScore(audioSamples: ShortArray, sampleRate: Int): Double? {
        val model = interpreter ?: return null
        if (sampleRate != EXPECTED_SAMPLE_RATE) return null
        if (audioSamples.size != EXPECTED_SAMPLES) return null

        var sumAbs = 0.0
        for (sample in audioSamples) {
            sumAbs += abs(sample / Short.MAX_VALUE.toFloat())
        }
        if (sumAbs / audioSamples.size < SILENCE_THRESHOLD) return 0.0

        val input = FloatArray(EXPECTED_SAMPLES)
        var maxAbs = 0f
        for (i in audioSamples.indices) {
            val normalized = audioSamples[i] / 32768f
            input[i] = normalized
            maxAbs = maxOf(maxAbs, abs(normalized))
        }
        if (maxAbs > 1f) {
            for (i in input.indices) {
                input[i] /= maxAbs
            }
        }

        val output = Array(1) { FloatArray(1) }
        model.run(arrayOf(input), output)
        return (output[0][0].toDouble() * 100.0).coerceAtMost(100.0)
    }

    private fun loadModelFile(assetName: String): MappedByteBuffer {
        context.assets.openFd(assetName).use { assetFd ->
            FileInputStream(assetFd.fileDescriptor).use { inputStream ->
                val channel = inputStream.channel
                return channel.map(
                    FileChannel.MapMode.READ_ONLY,
                    assetFd.startOffset,
                    assetFd.declaredLength,
                )
            }
        }
    }

    companion object {
        private const val EXPECTED_SAMPLE_RATE = 16_000
        private const val EXPECTED_SAMPLES = 16_000
        private const val SILENCE_THRESHOLD = 0.005
    }
}
