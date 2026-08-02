package com.safeher.app.feature.auth.util

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class AuthValidatorTest {

    @Test
    fun validatePhone_acceptsValidNumber() {
        assertThat(AuthValidator.validatePhone("9876543210")).isNull()
    }

    @Test
    fun validatePhone_rejectsBlank() {
        assertThat(AuthValidator.validatePhone("")).isEqualTo("Phone number is required")
    }

    @Test
    fun validatePhone_rejectsInvalidFormat() {
        assertThat(AuthValidator.validatePhone("123")).isNotNull()
    }

    @Test
    fun validatePassword_requiresMinimumLength() {
        assertThat(AuthValidator.validatePassword("12345")).isEqualTo("Password must be at least 6 characters")
        assertThat(AuthValidator.validatePassword("123456")).isNull()
    }

    @Test
    fun validateName_requiresNonBlank() {
        assertThat(AuthValidator.validateName("")).isEqualTo("Name is required")
        assertThat(AuthValidator.validateName("Jane")).isNull()
    }

    @Test
    fun validateOtp_requiresSixDigits() {
        assertThat(AuthValidator.validateOtp("12345")).isEqualTo("Enter the 6-digit OTP")
        assertThat(AuthValidator.validateOtp("123456")).isNull()
    }

    @Test
    fun passwordStrength_weakForShortPassword() {
        assertThat(AuthValidator.passwordStrength("abc")).isEqualTo(PasswordStrength.WEAK)
    }

    @Test
    fun passwordStrength_strongForLongMixedPassword() {
        assertThat(AuthValidator.passwordStrength("Secret12345")).isEqualTo(PasswordStrength.STRONG)
    }

    @Test
    fun normalizePhone_stripsSpaces() {
        assertThat(AuthValidator.normalizePhone("987 654 3210")).isEqualTo("9876543210")
    }
}
