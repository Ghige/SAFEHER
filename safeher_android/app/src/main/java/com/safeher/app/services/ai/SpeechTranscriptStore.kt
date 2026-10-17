package com.safeher.app.services.ai

import javax.inject.Inject
import javax.inject.Singleton

/**
 * Holds the latest speech transcript for phrase inference.
 * ASR writes here when active; tests/debug may [inject].
 */
@Singleton
class SpeechTranscriptStore @Inject constructor() {
    @Volatile
    var latestTranscript: String? = null
        private set

    @Volatile
    var asrActive: Boolean = false
        private set

    fun updateFromAsr(text: String?, isFinal: Boolean) {
        if (!text.isNullOrBlank()) {
            latestTranscript = text.trim()
        }
        if (isFinal && text.isNullOrBlank()) {
            // keep last non-empty
        }
    }

    fun setAsrActive(active: Boolean) {
        asrActive = active
        if (!active) {
            // leave last transcript for one more cycle
        }
    }

    /** Test / debug only — not used to fake model scores. */
    fun inject(transcript: String?) {
        latestTranscript = transcript?.trim()?.takeIf { it.isNotEmpty() }
    }

    fun clear() {
        latestTranscript = null
        asrActive = false
    }
}
