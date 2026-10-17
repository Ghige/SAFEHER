package com.safeher.app.services.ai

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage 4 — inference integration unit tests (no device / no fake production scores).
 */
class Stage4InferenceIntegrationTest {

    @Test
    fun speechCatalog_helpMe_feedsDecisionContractSde() {
        val store = SpeechTranscriptStore()
        store.inject("please help me")
        val engine = SpeechPhraseInferenceEngine(store)
        val phrase = engine.inferFromLatestTranscript()
        assertTrue(phrase.phraseDetected)
        assertTrue(phrase.phraseScore >= DecisionContract.PHRASE_MEDIUM)

        val decision = SafetyDecisionEngine.decide(
            speech = SafetyDecisionEngine.SpeechModelResult(
                phraseDetected = phrase.phraseDetected,
                phraseScore = phrase.phraseScore,
                language = phrase.language,
                phrase = phrase.phrase,
            ),
        )
        assertEquals(DecisionContract.STATE_SUSPICIOUS, decision.state)
        assertEquals(DecisionContract.ACTION_CONFIRM, decision.action)
        assertEquals(DecisionContract.CONFIRM_COUNTDOWN_SECONDS, decision.confirmCountdownSeconds)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }

    @Test
    fun movementEngine_unavailable_returnsNull_notFakeScore() = runBlocking {
        val engine = MissingMovementInferenceEngine()
        assertFalse(engine.isAvailable)
        assertNull(engine.inferMovement(FloatArray(128 * 3)))
        assertTrue(engine.unavailableReason.contains("joblib") || engine.unavailableReason.contains("tflite"))
    }

    @Test
    fun audioPipeline_unavailableEngine_returnsNull() = runBlocking {
        val store = SpeechTranscriptStore()
        val speech = SpeechPhraseInferenceEngine(store)
        val pipeline = AudioHybridPipeline(
            audioInferenceEngine = object : AudioInferenceEngine {
                override val isAvailable = false
                override val lastLatencyMs: Long? = null
                override val lastError: String? = "missing"
                override suspend fun inferDistressScore(audioSamples: ShortArray, sampleRate: Int) = null
            },
            speechPhraseInferenceEngine = speech,
            transcriptStore = store,
        )
        val buf = ShortArray(16_000)
        assertNull(pipeline.process(buf, 16_000))
    }

    @Test
    fun audioPipeline_realFakeScoresFromEngine_passIntoSde() = runBlocking {
        val store = SpeechTranscriptStore()
        store.inject("help me")
        val speech = SpeechPhraseInferenceEngine(store)
        val pipeline = AudioHybridPipeline(
            audioInferenceEngine = object : AudioInferenceEngine {
                override val isAvailable = true
                override val lastLatencyMs: Long? = 12
                override val lastError: String? = null
                override suspend fun inferDistressScore(audioSamples: ShortArray, sampleRate: Int) = 88.0
            },
            speechPhraseInferenceEngine = speech,
            transcriptStore = store,
        )
        // Non-silent buffer so feature extractor has energy
        val buf = ShortArray(16_000) { (10_000).toShort() }
        val result = pipeline.process(buf, 16_000)
        assertTrue(result != null)
        assertEquals(88.0, result!!.rawConfidence, 0.01)
        assertTrue(result.phraseScore >= DecisionContract.PHRASE_MEDIUM)
        assertEquals(DecisionContract.STATE_EMERGENCY, result.safetyDecision?.state)
        assertEquals(12L, result.audioLatencyMs)
    }

    @Test
    fun decisionContract_autoSosRemainsDisabled() {
        assertFalse(DecisionContract.CONFIRM_COUNTDOWN_SECONDS <= 0)
        assertEquals(30, DecisionContract.CONFIRM_COUNTDOWN_SECONDS)
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }
}
