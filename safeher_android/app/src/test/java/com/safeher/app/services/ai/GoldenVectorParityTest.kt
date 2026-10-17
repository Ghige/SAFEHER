package com.safeher.app.services.ai

import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage-3 golden vectors — Android must match shared golden_vectors.json expectations
 * (same inputs as Python unified / backend).
 *
 * Uses Moshi (not android.jar org.json stubs) so JVM unit tests work.
 */
class GoldenVectorParityTest {

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test
    fun decisionContractConstantsMatchBundledJson() {
        val raw = readResource("decision_contract.json")
        val json = moshi.adapter(ContractFile::class.java).fromJson(raw)
            ?: error("Failed to parse decision_contract.json")

        assertEquals(DecisionContract.CONTRACT_VERSION, json.contract_version)
        assertTrue(json.DEMO_MODE)
        assertFalse(json.AI_AUTO_SOS_ENABLED)

        val gates = json.gates
        assertEquals(DecisionContract.DISTRESS_MEDIUM, gates.distress_medium, 1e-9)
        assertEquals(DecisionContract.DISTRESS_HIGH, gates.distress_high, 1e-9)
        assertEquals(DecisionContract.PHRASE_MEDIUM, gates.phrase_medium, 1e-9)
        assertEquals(DecisionContract.PHRASE_HIGH, gates.phrase_high, 1e-9)
        assertEquals(DecisionContract.MOVE_MEDIUM, gates.movement_medium, 1e-9)
        assertEquals(DecisionContract.MOVE_HIGH, gates.movement_high, 1e-9)
        assertEquals(DecisionContract.VOLUME_LOUD, gates.volume_loud, 1e-9)
        assertEquals(DecisionContract.DISTRESS_FLOOR_HIGH, gates.distress_floor_high, 1e-9)

        val bands = json.risk_bands
        assertEquals(DecisionContract.RISK_SILENT, bands.silent, 1e-9)
        assertEquals(DecisionContract.RISK_MEDIUM, bands.medium, 1e-9)
        assertEquals(DecisionContract.RISK_HIGH, bands.high, 1e-9)

        val conf = json.confirmation
        assertEquals(DecisionContract.ACTION_CONFIRM, conf.api_action_name)
        assertEquals(DecisionContract.CONFIRM_COUNTDOWN_SECONDS, conf.countdown_seconds)
        assertEquals(30, conf.countdown_seconds)
    }

    @Test
    fun goldenVectorsMatchExpectedActionsAndStates() {
        val raw = readResource("golden_vectors.json")
        val root = moshi.adapter(GoldenFile::class.java).fromJson(raw)
            ?: error("Failed to parse golden_vectors.json")
        assertEquals(DecisionContract.CONTRACT_VERSION, root.contract_version)
        assertTrue(root.vectors.size >= 8)

        for (v in root.vectors) {
            val decision = SafetyDecisionEngine.decide(
                audio = SafetyDecisionEngine.AudioModelResult(
                    distressScore = v.audio,
                    volumeScore = v.volume,
                ),
                speech = SafetyDecisionEngine.SpeechModelResult(
                    phraseScore = v.speech,
                    phraseDetected = v.speech >= DecisionContract.PHRASE_MEDIUM,
                ),
                movement = SafetyDecisionEngine.MovementModelResult(
                    movementAnomalyScore = v.movement,
                    fallDetected = v.fall,
                ),
            )
            assertEquals("action mismatch for ${v.id}", v.expected_action, decision.action)
            assertEquals("state mismatch for ${v.id}", v.expected_state, decision.state)
            assertEquals(
                DecisionContract.CONFIRM_COUNTDOWN_SECONDS,
                decision.confirmCountdownSeconds,
            )
        }
    }

    private fun readResource(name: String): String {
        val loader = requireNotNull(javaClass.classLoader) { "classLoader null" }
        val stream = requireNotNull(loader.getResourceAsStream(name)) {
            "Missing test resource: $name"
        }
        return stream.bufferedReader().use { it.readText() }
    }

    @JsonClass(generateAdapter = false)
    data class ContractFile(
        val contract_version: String,
        val DEMO_MODE: Boolean,
        val AI_AUTO_SOS_ENABLED: Boolean,
        val gates: Gates,
        val risk_bands: RiskBands,
        val confirmation: Confirmation,
    )

    @JsonClass(generateAdapter = false)
    data class Gates(
        val distress_medium: Double,
        val distress_high: Double,
        val phrase_medium: Double,
        val phrase_high: Double,
        val movement_medium: Double,
        val movement_high: Double,
        val volume_loud: Double,
        val distress_floor_high: Double,
    )

    @JsonClass(generateAdapter = false)
    data class RiskBands(
        val silent: Double,
        val medium: Double,
        val high: Double,
    )

    @JsonClass(generateAdapter = false)
    data class Confirmation(
        val api_action_name: String,
        val countdown_seconds: Int,
    )

    @JsonClass(generateAdapter = false)
    data class GoldenFile(
        val contract_version: String,
        val vectors: List<GoldenVector>,
    )

    @JsonClass(generateAdapter = false)
    data class GoldenVector(
        val id: String,
        val audio: Double,
        val speech: Double,
        val movement: Double,
        val volume: Double = 0.0,
        val fall: Boolean = false,
        val expected_action: String,
        val expected_state: String,
    )
}
