package com.safeher.app.services.ai

/**
 * Text-layer emergency phrase detector.
 * Feed ASR / typed transcript when available; returns phrase_score in 0–1.
 */
object EmergencyPhraseDetector {

    data class Result(
        val phraseDetected: Boolean,
        val phraseScore: Double,
        val language: String? = null,
        val phrase: String? = null,
    )

    fun detect(transcript: String?): Result {
        val norm = EmergencyPhraseCatalog.normalize(transcript.orEmpty())
        if (norm.isEmpty()) {
            return Result(false, 0.0)
        }

        var bestScore = 0.0
        var bestPhrase: String? = null
        var bestLang: String? = null

        for (entry in EmergencyPhraseCatalog.all()) {
            val phrase = EmergencyPhraseCatalog.normalize(entry.phrase)
            if (phrase.isEmpty()) continue

            val score = when {
                norm == phrase || norm.contains(phrase) || phrase.contains(norm) -> 1.0
                else -> tokenOverlapScore(norm, phrase)
            }
            if (score > bestScore) {
                bestScore = score
                bestPhrase = phrase
                bestLang = entry.language
            }
        }

        return Result(
            phraseDetected = bestScore >= DecisionContract.PHRASE_MEDIUM,
            phraseScore = bestScore,
            language = bestLang,
            phrase = bestPhrase,
        )
    }

    private fun tokenOverlapScore(norm: String, phrase: String): Double {
        val pToks = phrase.split(" ").filter { it.isNotEmpty() }.toSet()
        val nToks = norm.split(" ").filter { it.isNotEmpty() }.toSet()
        if (pToks.isEmpty()) return 0.0
        val overlap = pToks.intersect(nToks).size.toDouble() / pToks.size
        return if (overlap >= 0.67) 0.55 + 0.35 * overlap else 0.0
    }
}
