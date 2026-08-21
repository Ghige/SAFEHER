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

    private val yamnetInterpreter: Interpreter?
    private val classifierInterpreter: Interpreter?

    override val isAvailable: Boolean

    init {
        yamnetInterpreter = loadInterpreter(
            assetName = AiModelAssets.YAMNET_EMBEDDING_MODEL,
            description = "YAMNet embedding model",
        )

        classifierInterpreter = loadInterpreter(
            assetName = AiModelAssets.AUDIO_CLASSIFIER_MODEL,
            description = "SafeHer V2 classifier",
        )

        isAvailable =
            yamnetInterpreter != null &&
            classifierInterpreter != null

        if (isAvailable) {
            Timber.i("SafeHer V2 audio inference pipeline ready")
        } else {
            Timber.e("SafeHer V2 audio inference pipeline unavailable")
        }
    }

    override suspend fun inferDistressScore(
        audioSamples: ShortArray,
        sampleRate: Int,
    ): Double? {

        val yamnet = yamnetInterpreter ?: return null
        val classifier = classifierInterpreter ?: return null

        if (sampleRate != EXPECTED_SAMPLE_RATE) {
            Timber.w(
                "Unexpected audio sample rate: %d, expected %d",
                sampleRate,
                EXPECTED_SAMPLE_RATE,
            )
            return null
        }

        if (audioSamples.size != EXPECTED_SAMPLES) {
            Timber.w(
                "Unexpected audio sample count: %d, expected %d",
                audioSamples.size,
                EXPECTED_SAMPLES,
            )
            return null
        }

        // ---------------------------------------------------------
        // 1. Silence check
        // ---------------------------------------------------------

        var sumAbs = 0.0

        for (sample in audioSamples) {
            sumAbs += abs(sample / 32768.0)
        }

        val meanAbsoluteAmplitude =
            sumAbs / audioSamples.size

        if (meanAbsoluteAmplitude < SILENCE_THRESHOLD) {
            return 0.0
        }

        // ---------------------------------------------------------
        // 2. Convert PCM ShortArray → normalized float waveform
        // ---------------------------------------------------------

        val waveform = FloatArray(EXPECTED_SAMPLES)

        for (i in audioSamples.indices) {
            waveform[i] = audioSamples[i] / 32768.0f
        }

        // YAMNet TFLite input:
        // [1, 16000]
        val yamnetInput = arrayOf(waveform)

        // YAMNet TFLite output:
        // [1, 1024]
        val embeddingOutput =
            Array(1) { FloatArray(EMBEDDING_SIZE) }

        // ---------------------------------------------------------
        // 3. Run YAMNet
        // ---------------------------------------------------------

        try {
            yamnet.run(
                yamnetInput,
                embeddingOutput,
            )
        } catch (e: Exception) {
            Timber.e(e, "YAMNet inference failed")
            return null
        }

        // ---------------------------------------------------------
        // 4. Run SafeHer classifier
        // ---------------------------------------------------------

        val classifierOutput =
            Array(1) { FloatArray(1) }

        try {
            classifier.run(
                embeddingOutput,
                classifierOutput,
            )
        } catch (e: Exception) {
            Timber.e(e, "SafeHer classifier inference failed")
            return null
        }

        // ---------------------------------------------------------
        // 5. Convert sigmoid probability → 0–100 confidence
        // ---------------------------------------------------------

        val probability =
            classifierOutput[0][0]
                .toDouble()
                .coerceIn(0.0, 1.0)

        val distressScore =
            probability * 100.0

        Timber.d(
            "SafeHer V2 distress score: %.2f",
            distressScore,
        )

        return distressScore
    }

    private fun loadInterpreter(
        assetName: String,
        description: String,
    ): Interpreter? {

        return try {

            val modelBuffer =
                loadModelFile(assetName)

            Interpreter(modelBuffer).also {

                Timber.i(
                    "Loaded %s: %s",
                    description,
                    assetName,
                )

                val inputShape =
                    it.getInputTensor(0).shape()

                val outputShape =
                    it.getOutputTensor(0).shape()

                Timber.i(
                    "%s input shape=%s output shape=%s",
                    description,
                    inputShape.contentToString(),
                    outputShape.contentToString(),
                )
            }

        } catch (e: Exception) {

            Timber.e(
                e,
                "Failed to load %s: %s",
                description,
                assetName,
            )

            null
        }
    }

    private fun loadModelFile(
        assetName: String,
    ): MappedByteBuffer {

        context.assets
            .openFd(assetName)
            .use { assetFd ->

                FileInputStream(
                    assetFd.fileDescriptor,
                ).use { inputStream ->

                    return inputStream.channel.map(
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

        private const val EMBEDDING_SIZE = 1024

        private const val SILENCE_THRESHOLD = 0.005
    }
}