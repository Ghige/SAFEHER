package com.safeher.app.feature.contacts.util

object ContactValidator {

    private val phoneRegex = Regex("^[0-9]{10}$")

    fun validateName(name: String): String? = when {
        name.isBlank() -> "Name is required"
        else -> null
    }

    fun validatePhone(phone: String): String? {
        val normalized = phone.replace(" ", "")
        return when {
            normalized.isBlank() -> "Phone number is required"
            !phoneRegex.matches(normalized) -> "Enter a valid 10-digit phone number"
            else -> null
        }
    }

    fun validateRelationship(relationship: String): String? = when {
        relationship.isBlank() -> "Relationship is required"
        else -> null
    }

    fun validateRingPriority(priority: Int): String? = when {
        priority !in 1..5 -> "Ring priority must be between 1 and 5"
        else -> null
    }

    fun normalizePhone(phone: String): String = phone.replace(" ", "")
}
