package com.safeher.app.services.ai

/**
 * Stage-4 analysis: how speech transcripts coexist with continuous AudioRecord.
 *
 * ## Constraint
 * Android allows only one active mic client. [android.media.AudioRecord] (distress TFLite)
 * and [android.speech.SpeechRecognizer] cannot run concurrently.
 *
 * ## Options considered
 * 1. **Exclusive modes** — AudioRecord OR ASR. Safe, but phrases never heard during distress monitoring.
 * 2. **Cloud ASR on uploaded PCM** — needs network; not reliable offline; privacy cost.
 * 3. **On-device KWS TFLite on same PCM** — safest long-term, but we have no keyword TFLite
 *    (speech_v2 is sklearn joblib) — inventing one would violate Stage-4 rules.
 * 4. **Duty-cycled interleave** — briefly pause AudioRecord, one-shot ASR, resume.
 *    Tradeoff: short audio blind spots (~2–3s every N seconds). Skip slots when local SDE
 *    is already SUSPICIOUS/EMERGENCY so distress capture stays continuous under threat.
 *
 * ## Chosen strategy (safest practical with existing assets)
 * **Duty-cycled interleave while local state is NORMAL**, gated by
 * [AiFeatureFlags.SPEECH_ASR_INTERLEAVE_ENABLED]. Catalog matcher always ready;
 * sklearn speech_v2 remains unsupported on-device.
 */
object SpeechAudioCoexistencePolicy {
    /** Time between ASR slots while continuous audio is the primary path. */
    const val INTERLEAVE_PERIOD_MS = 20_000L

    /** Max time to hold the mic for one ASR attempt. */
    const val ASR_SLOT_MS = 2_800L

    /** Do not steal mic when local fusion is already elevated. */
    fun shouldDeferAsrForLocalState(state: String?): Boolean {
        return state == DecisionContract.STATE_SUSPICIOUS ||
            state == DecisionContract.STATE_EMERGENCY
    }

    const val STRATEGY_SUMMARY =
        "Primary=continuous AudioRecord+TFLite; Secondary=duty-cycled one-shot ASR " +
            "only while local SDE is NORMAL; catalog always on; no concurrent mic clients."
}
