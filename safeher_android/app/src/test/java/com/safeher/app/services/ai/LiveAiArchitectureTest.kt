package com.safeher.app.services.ai

import com.safeher.app.BuildConfig
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage 3 live-AI architecture: 1 s hops, temporal history, popup UI gates,
 * confirm-first, auto SOS remains off. Does not load the production TFLite file.
 */
class LiveAiArchitectureTest {

    private val config = AiDetectionConfig()

    @Test
    fun oneSecondWindows_feedScoreHistoryAndTemporalDecision() = runBlocking {
        val store = SpeechTranscriptStore()
        val scores = ArrayDeque(listOf(20.0, 88.0, 89.0, 90.0))
        val pipeline = AudioHybridPipeline(
            audioInferenceEngine = scriptedEngine(scores),
            speechPhraseInferenceEngine = SpeechPhraseInferenceEngine(store),
            transcriptStore = store,
        )
        val buf = ShortArray(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES) { 10_000 }
        val rate = CompletedAudioWindow.PRODUCTION_SAMPLE_RATE_HZ

        val first = pipeline.process(buf, rate, windowSequence = 1, windowTimestampMs = 1_000L)!!
        assertEquals(1L, first.windowSequence)
        assertEquals(1_000L, first.windowTimestampMs)
        assertEquals(TemporalState.NONE, first.temporalDecision!!.state)
        assertFalse(first.temporalDecision!!.isSustained)

        val second = pipeline.process(buf, rate, windowSequence = 2, windowTimestampMs = 2_000L)!!
        assertEquals(TemporalState.WATCH, second.temporalDecision!!.state)
        val third = pipeline.process(buf, rate, windowSequence = 3, windowTimestampMs = 3_000L)!!
        assertEquals(TemporalState.WATCH, third.temporalDecision!!.state)
        val fourth = pipeline.process(buf, rate, windowSequence = 4, windowTimestampMs = 4_000L)!!
        assertEquals(TemporalState.SUSTAINED, fourth.temporalDecision!!.state)
        assertTrue(fourth.temporalDecision!!.isSustained)
        assertEquals(4L, fourth.windowSequence)
    }

    @Test
    fun cooldownAndVisiblePopup_keepScoring() {
        val history = ScoreHistory(config.evidenceHorizonSeconds, config.rollingWindowSize)
        val decider = SustainedDistressDecider(config)
        val popup = PopupEligibilityController(config)

        fun score(seq: Long, t: Long, value: Double): TemporalDecision {
            history.add(ScoreSample(seq, t, value), nowMs = t)
            return decider.evaluate(history.snapshot(), nowMs = t)
        }

        score(1, 1_000L, 80.0)
        score(2, 2_000L, 81.0)
        val sustained = score(3, 3_000L, 82.0)
        assertTrue(sustained.isSustained)

        val eligible = popup.evaluate(3_000L, sustained, 82.0)
        assertTrue(eligible.eligible)
        popup.onPopupShown(sustained.episodeId, 82.0, 3_000L)

        val duringPopup = score(4, 4_000L, 83.0)
        assertTrue(duringPopup.isSustained)
        val visible = popup.evaluate(4_000L, duringPopup, 83.0)
        assertEquals(PopupSuppressionReason.POPUP_VISIBLE, visible.suppressionReason)
        assertTrue(visible.inferenceContinues)
        assertEquals(4, history.size)

        popup.onPopupDismissed(5_000L)
        val afterDismiss = score(5, 6_000L, 84.0)
        val cooled = popup.evaluate(6_000L, afterDismiss, 84.0)
        assertEquals(PopupSuppressionReason.COOLDOWN, cooled.suppressionReason)
        assertTrue(cooled.inferenceContinues)
        assertTrue(history.size >= 3)
    }

    @Test
    fun confirmFirst_yesNoTimeout_neverAutoSos() {
        assertFalse(BuildConfig.AI_AUTO_SOS_ENABLED)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)

        val yes = AiConfirmFirstPolicy.resolve(
            userConfirmed = true,
            timedOut = false,
            recommendedAction = DecisionContract.ACTION_CONFIRM,
            autoSosEnabled = AiFeatureFlags.AI_AUTO_SOS_ENABLED,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.USER_CONFIRMED_MANUAL_SOS, yes)
        assertTrue(AiConfirmFirstPolicy.opensManualSosCountdown(yes))
        assertFalse(AiConfirmFirstPolicy.createsAlert(yes))

        val no = AiConfirmFirstPolicy.resolve(
            userConfirmed = false,
            timedOut = false,
            recommendedAction = DecisionContract.ACTION_FIRE,
            autoSosEnabled = false,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.CANCELLED_NO_ALERT, no)
        assertFalse(AiConfirmFirstPolicy.createsAlert(no))

        val timeout = AiConfirmFirstPolicy.resolve(
            userConfirmed = null,
            timedOut = true,
            recommendedAction = DecisionContract.ACTION_FIRE,
            autoSosEnabled = false,
        )
        assertEquals(AiConfirmFirstPolicy.Outcome.NO_RESPONSE_DISMISS_SAFE, timeout)
        assertFalse(AiConfirmFirstPolicy.createsAlert(timeout))
    }

    private fun scriptedEngine(scores: ArrayDeque<Double>): AudioInferenceEngine =
        object : AudioInferenceEngine {
            override val isAvailable = true
            override val lastLatencyMs: Long? = 5
            override val lastError: String? = null
            override suspend fun inferDistressScore(
                audioSamples: ShortArray,
                sampleRate: Int,
            ): Double? {
                assertEquals(CompletedAudioWindow.PRODUCTION_WINDOW_SAMPLES, audioSamples.size)
                assertEquals(CompletedAudioWindow.PRODUCTION_SAMPLE_RATE_HZ, sampleRate)
                return scores.removeFirst()
            }
        }
}
