package com.safeher.app.services.ai

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import timber.log.Timber
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume

/**
 * On-device ASR for emergency phrases.
 *
 * Must not run concurrently with AudioRecord. Coordinator pauses mic first
 * (see [SpeechAudioCoexistencePolicy]).
 */
@Singleton
class SpeechAsrController @Inject constructor(
    @ApplicationContext private val context: Context,
    private val transcriptStore: SpeechTranscriptStore,
) {
    private var recognizer: SpeechRecognizer? = null
    private var continuous = false
    private val mainHandler = Handler(Looper.getMainLooper())

    val isAvailable: Boolean
        get() = SpeechRecognizer.isRecognitionAvailable(context)

    /** Continuous ASR when mic is fully free (audio capture disabled). */
    fun start() {
        if (continuous) return
        if (!isAvailable) {
            Timber.w("SpeechRecognizer not available on this device")
            transcriptStore.setAsrActive(false)
            return
        }
        continuous = true
        transcriptStore.setAsrActive(true)
        mainHandler.post {
            try {
                ensureRecognizer()
                startListening(loop = true)
                Timber.i("Speech ASR continuous started")
            } catch (e: Exception) {
                Timber.e(e, "Failed to start continuous SpeechRecognizer")
                stop()
            }
        }
    }

    fun stop() {
        continuous = false
        transcriptStore.setAsrActive(false)
        mainHandler.post {
            try {
                recognizer?.stopListening()
                recognizer?.cancel()
                recognizer?.destroy()
            } catch (e: Exception) {
                Timber.w(e, "SpeechRecognizer stop error")
            }
            recognizer = null
        }
    }

    /**
     * One-shot recognition for duty-cycled interleave. Caller must pause AudioRecord first.
     * @return best transcript or null
     */
    suspend fun runOneShot(timeoutMs: Long = SpeechAudioCoexistencePolicy.ASR_SLOT_MS): String? {
        if (!isAvailable) return null
        return withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine { cont ->
                mainHandler.post {
                    try {
                        ensureRecognizer()
                        val listener = object : RecognitionListener {
                            override fun onReadyForSpeech(params: Bundle?) = Unit
                            override fun onBeginningOfSpeech() = Unit
                            override fun onRmsChanged(rmsdB: Float) = Unit
                            override fun onBufferReceived(buffer: ByteArray?) = Unit
                            override fun onEndOfSpeech() = Unit
                            override fun onEvent(eventType: Int, params: Bundle?) = Unit
                            override fun onPartialResults(partialResults: Bundle?) {
                                val text = partialResults
                                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                                    ?.firstOrNull()
                                if (!text.isNullOrBlank()) {
                                    transcriptStore.updateFromAsr(text, isFinal = false)
                                }
                            }

                            override fun onError(error: Int) {
                                Timber.d("ASR one-shot error=%d", error)
                                transcriptStore.setAsrActive(false)
                                if (cont.isActive) cont.resume(null)
                            }

                            override fun onResults(results: Bundle?) {
                                val text = results
                                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                                    ?.firstOrNull()
                                transcriptStore.updateFromAsr(text, isFinal = true)
                                transcriptStore.setAsrActive(false)
                                AiDetectionLogger.logSpeechTranscript(text, isFinal = true)
                                if (cont.isActive) cont.resume(text)
                            }
                        }
                        recognizer?.setRecognitionListener(listener)
                        transcriptStore.setAsrActive(true)
                        startListening(loop = false)
                    } catch (e: Exception) {
                        Timber.e(e, "ASR one-shot failed")
                        transcriptStore.setAsrActive(false)
                        if (cont.isActive) cont.resume(null)
                    }
                }
                cont.invokeOnCancellation {
                    mainHandler.post {
                        try {
                            recognizer?.cancel()
                        } catch (_: Exception) {
                        }
                        transcriptStore.setAsrActive(false)
                    }
                }
            }
        }.also {
            transcriptStore.setAsrActive(false)
        }
    }

    private fun ensureRecognizer() {
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        }
    }

    private fun startListening(loop: Boolean) {
        val sr = recognizer ?: return
        if (loop) {
            sr.setRecognitionListener(continuousListener)
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }
        sr.startListening(intent)
    }

    private val continuousListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit

        override fun onError(error: Int) {
            Timber.d("SpeechRecognizer continuous error=%d", error)
            if (continuous) {
                mainHandler.postDelayed({ startListening(loop = true) }, 400)
            }
        }

        override fun onResults(results: Bundle?) {
            val texts = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val best = texts?.firstOrNull()
            transcriptStore.updateFromAsr(best, isFinal = true)
            AiDetectionLogger.logSpeechTranscript(best, isFinal = true)
            if (continuous) {
                mainHandler.post { startListening(loop = true) }
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val texts = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val best = texts?.firstOrNull()
            transcriptStore.updateFromAsr(best, isFinal = false)
            if (!best.isNullOrBlank()) {
                AiDetectionLogger.logSpeechTranscript(best, isFinal = false)
            }
        }
    }
}
