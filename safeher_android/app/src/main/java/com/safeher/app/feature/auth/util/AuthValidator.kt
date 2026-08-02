package com.safeher.app.feature.auth.util

enum class PasswordStrength {
    WEAK,
    FAIR,
    STRONG,
}

object AuthValidator {

    private val phoneRegex = Regex("^\\+?[0-9]{10,15}$")

    fun validatePhone(phone: String): String? {
        val normalized = phone.replace(" ", "")
        if (normalized.isBlank()) return "Phone number is required"
        if (!phoneRegex.matches(normalized)) return "Enter a valid 10–15 digit phone number"
        return null
    }

    fun validatePassword(password: String): String? = when {
        password.isBlank() -> "Password is required"
        password.length < 6 -> "Password must be at least 6 characters"
        else -> null
    }

    fun validateName(name: String): String? = when {
        name.isBlank() -> "Name is required"
        name.length > 100 -> "Name is too long"
        else -> null
    }

    fun validateOtp(otp: String): String? = when {
        otp.length != 6 -> "Enter the 6-digit OTP"
        !otp.all { it.isDigit() } -> "OTP must contain digits only"
        else -> null
    }

    fun passwordStrength(password: String): PasswordStrength = when {
        password.length < 6 -> PasswordStrength.WEAK
        password.length < 10 || !hasMixedCaseAndDigit(password) -> PasswordStrength.FAIR
        else -> PasswordStrength.STRONG
    }

    private fun hasMixedCaseAndDigit(password: String): Boolean {
        val hasDigit = password.any { it.isDigit() }
        val hasLetter = password.any { it.isLetter() }
        return hasDigit && hasLetter
    }

    fun normalizePhone(phone: String): String = phone.replace(" ", "")
}
