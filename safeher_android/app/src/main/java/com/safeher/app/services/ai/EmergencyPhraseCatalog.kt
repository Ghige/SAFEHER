package com.safeher.app.services.ai

/**
 * Extensible emergency phrase catalog (EN / HI / MR seed).
 * Add languages/phrases without changing Safety Decision Engine code.
 */
object EmergencyPhraseCatalog {

    data class Entry(val language: String, val phrase: String)

    /** Seed phrases — not a permanent closed set. */
    val DEFAULT: List<Entry> = listOf(
        Entry("english", "help me"),
        Entry("english", "save me"),
        Entry("english", "please help"),
        Entry("english", "i need help"),
        Entry("english", "need help"),
        Entry("english", "call police"),
        Entry("english", "call the police"),
        Entry("english", "send help"),
        Entry("hindi", "bachao"),
        Entry("hindi", "mujhe bachao"),
        Entry("hindi", "madad karo"),
        Entry("hindi", "madad"),
        Entry("marathi", "madat kara"),
        Entry("marathi", "madat karo"),
        Entry("marathi", "mala vachva"),
        Entry("marathi", "vachva"),
        Entry("marathi", "madat"),
    )

    private val extra = mutableListOf<Entry>()

    fun all(): List<Entry> = DEFAULT + extra

    fun addPhrase(language: String, phrase: String) {
        val normalized = normalize(phrase)
        if (normalized.isNotEmpty()) {
            extra.add(Entry(language.lowercase(), normalized))
        }
    }

    fun normalize(text: String): String =
        text.lowercase()
            .replace(Regex("[^\\p{L}\\p{N}\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
}
