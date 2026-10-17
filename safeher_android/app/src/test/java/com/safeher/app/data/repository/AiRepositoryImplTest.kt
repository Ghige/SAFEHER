package com.safeher.app.data.repository

import com.safeher.app.core.network.AiApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.AiConfidenceResponseDto
import com.safeher.app.data.remote.dto.AiFusionDto
import com.safeher.app.data.remote.dto.AiSosResponseDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AiRepositoryImplTest {

    private val api: AiApi = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: AiRepositoryImpl

    private val confidenceResponse = AiConfidenceResponseDto(
        total_score = 70.0,
        action = "confirm_30s",
        activate_gps_stream = false,
        audio_score = 80.0,
        movement_score = 70.0,
        heart_rate_spike = false,
        is_night = true,
        is_isolated = false,
    )

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        repository = AiRepositoryImpl(api, networkMonitor, moshi)
    }

    @Test
    fun getConfidence_mapsResponseToDomain() = runTest {
        coEvery { api.getConfidence(any()) } returns confidenceResponse

        val result = repository.getConfidence(
            audioScore = 80f,
            movementScore = 70f,
            isNight = true,
        )

        assertTrue(result.isSuccess)
        assertEquals(70.0, result.getOrNull()!!.totalScore, 0.01)
        assertEquals(com.safeher.app.domain.model.AiAction.CONFIRM_30S, result.getOrNull()!!.action)
    }

    @Test
    fun triggerAudioSos_returnsAlertId() = runTest {
        coEvery { api.triggerAudioSos(any()) } returns AiSosResponseDto(
            fusion = AiFusionDto(
                total_score = 95.0,
                action = "fire_immediately",
                activate_gps_stream = true,
                audio_score = 95.0,
                movement_score = 95.0,
                heart_rate_spike = false,
                is_night = true,
                is_isolated = true,
            ),
            alert = "550e8400-e29b-41d4-a716-446655440000",
        )

        val result = repository.triggerAudioSos(audioScore = 95f, movementScore = 95f)

        assertTrue(result.isSuccess)
        assertEquals("550e8400-e29b-41d4-a716-446655440000", result.getOrNull()!!.alertId)
        coVerify { api.triggerAudioSos(any()) }
    }

    @Test
    fun triggerMovementSos_returnsTriggerError() = runTest {
        coEvery { api.triggerMovementSos(any()) } returns AiSosResponseDto(
            fusion = null,
            alert = null,
            trigger_error = "No emergency contacts configured",
            reason = "trigger_failed",
        )

        val result = repository.triggerMovementSos(movementScore = 95f, fallDetected = true)

        assertTrue(result.isSuccess)
        assertNull(result.getOrNull()!!.alertId)
        assertEquals("No emergency contacts configured", result.getOrNull()!!.triggerError)
    }

    @Test
    fun getConfidence_offline_returnsFailure() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.getConfidence(audioScore = 80f, movementScore = 70f)

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("offline", ignoreCase = true) == true)
    }

    @Test
    fun submitFeedback_postsMetadataOnly() = runTest {
        coEvery { api.submitFeedback(any()) } returns com.safeher.app.data.remote.dto.AiFeedbackResponseDto(
            event_id = "11111111-1111-1111-1111-111111111111",
            candidate_category = "AI_FALSE_POSITIVE_CANDIDATE",
            review_status = "UNREVIEWED",
            gold_eligible = false,
            fp_fn_status = "HARD_NEGATIVE_CANDIDATE",
        )

        val result = repository.submitFeedback(
            eventId = "11111111-1111-1111-1111-111111111111",
            sessionId = "22222222-2222-2222-2222-222222222222",
            modelVersion = "v1.0",
            signalType = "audio",
            predictionState = "EMERGENCY",
            confidence = 90.0,
            userFeedback = "CANCELLED",
            outcome = "NO_ALERT",
            consentGranted = true,
            consentVersion = "privacy-v2-metadata-only",
            featuresJson = """{"rms":0.1}""",
        )

        assertTrue(result.isSuccess)
        coVerify { api.submitFeedback(any()) }
    }
}
