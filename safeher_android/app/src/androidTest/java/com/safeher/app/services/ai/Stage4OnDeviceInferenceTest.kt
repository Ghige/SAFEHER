package com.safeher.app.services.ai

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import kotlin.math.PI
import kotlin.math.sin

/**
 * Stage-4 on-device / emulator tests — requires a running device or AVD.
 * Exercises real TFLite asset load + synthetic PCM → score → DecisionContract SDE.
 * Does not enable AI auto-SOS or send alerts.
 */
@RunWith(AndroidJUnit4::class)
class Stage4OnDeviceInferenceTest {

    @Test
    fun audioTfliteAsset_loadsAndInfers_thenSdeProducesAction() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertTrue(
            "yamnet asset missing",
            context.assets.list("")?.contains(AiModelAssets.AUDIO_MODEL) == true,
        )

        val model = loadModel(context, AiModelAssets.AUDIO_MODEL)
        val interpreter = Interpreter(model)
        try {
            val silence = ShortArray(16_000)
            val silenceScore = runModel(interpreter, silence)
            assertNotNull(silenceScore)
            assertTrue("silence score in range", silenceScore!! in 0.0..100.0)

            // Loudish 1 kHz tone — proves non-null inference; not claimed as distress label.
            val tone = ShortArray(16_000) { i ->
                (sin(2.0 * PI * 1000.0 * i / 16_000.0) * 20_000).toInt().toShort()
            }
            val toneScore = runModel(interpreter, tone)
            assertNotNull(toneScore)
            assertTrue(toneScore in 0.0..100.0)

            // Engine silence short-circuit (mean abs < 0.005) returns 0 without model — verify path.
            val nearSilent = ShortArray(16_000) { 1 }
            var sumAbs = 0.0
            for (s in nearSilent) sumAbs += kotlin.math.abs(s / Short.MAX_VALUE.toFloat())
            assertTrue(
                "fixture remains below engine silence gate",
                sumAbs / nearSilent.size < 0.005,
            )

            val decision = SafetyDecisionEngine.decide(
                audio = SafetyDecisionEngine.AudioModelResult(
                    distressScore = (toneScore / 100.0).coerceIn(0.0, 1.0),
                    audioConfidence = toneScore / 100.0,
                    volumeScore = 0.5,
                ),
            )
            assertNotNull(decision.state)
            assertTrue(
                decision.action in setOf(
                    DecisionContract.ACTION_NOTHING,
                    DecisionContract.ACTION_SILENT,
                    DecisionContract.ACTION_CONFIRM,
                    DecisionContract.ACTION_FIRE,
                ),
            )
            assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
            assertEquals(DecisionContract.CONTRACT_VERSION, decision.contractVersion)

            // Record observed scores for the Stage-4 log (not pass/fail gates on absolute distress).
            android.util.Log.i(
                "Stage4OnDevice",
                "tflite_ok silenceScore=$silenceScore toneScore=$toneScore sde=${decision.state}/${decision.action}",
            )
        } finally {
            interpreter.close()
        }
    }

    @Test
    fun movementTflite_notBundled_documented() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val names = context.assets.list("")?.toList().orEmpty()
        assertFalse(
            "movement TFLite must not be faked into assets",
            names.contains(AiModelAssets.MOVEMENT_MODEL),
        )
        assertFalse(AiFeatureFlags.MOVEMENT_AI_ENABLED)
    }

    @Test
    fun multimodal_syntheticScores_agreeWithDecisionContract() {
        // Real DecisionContract fusion with synthetic but non-fake policy inputs
        // (same golden path as unit tests — validates on-device SDE binary).
        val d = SafetyDecisionEngine.decide(
            audio = SafetyDecisionEngine.AudioModelResult(distressScore = 0.86),
            speech = SafetyDecisionEngine.SpeechModelResult(
                phraseDetected = true,
                phraseScore = 0.9,
                phrase = "help me",
            ),
            movement = SafetyDecisionEngine.MovementModelResult(movementAnomalyScore = 0.85),
        )
        assertEquals(DecisionContract.STATE_EMERGENCY, d.state)
        assertEquals(DecisionContract.ACTION_FIRE, d.action)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }

    private fun loadModel(context: Context, asset: String): MappedByteBuffer {
        context.assets.openFd(asset).use { fd ->
            FileInputStream(fd.fileDescriptor).use { input ->
                return input.channel.map(
                    FileChannel.MapMode.READ_ONLY,
                    fd.startOffset,
                    fd.declaredLength,
                )
            }
        }
    }

    private fun runModel(interpreter: Interpreter, samples: ShortArray): Double {
        val input = FloatArray(16_000)
        for (i in samples.indices) {
            input[i] = samples[i] / 32768f
        }
        val output = Array(1) { FloatArray(1) }
        interpreter.run(arrayOf(input), output)
        return (output[0][0].toDouble() * 100.0).coerceIn(0.0, 100.0)
    }
}
