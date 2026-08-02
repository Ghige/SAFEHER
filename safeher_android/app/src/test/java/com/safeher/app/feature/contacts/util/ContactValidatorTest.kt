package com.safeher.app.feature.contacts.util

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ContactValidatorTest {

    @Test
    fun validateName_requiresNonBlank() {
        assertThat(ContactValidator.validateName("")).isEqualTo("Name is required")
        assertThat(ContactValidator.validateName("Mom")).isNull()
    }

    @Test
    fun validatePhone_requiresTenDigits() {
        assertThat(ContactValidator.validatePhone("123")).isNotNull()
        assertThat(ContactValidator.validatePhone("9876543210")).isNull()
    }

    @Test
    fun validateRelationship_requiresNonBlank() {
        assertThat(ContactValidator.validateRelationship("")).isEqualTo("Relationship is required")
        assertThat(ContactValidator.validateRelationship("Mother")).isNull()
    }

    @Test
    fun validateRingPriority_allowsOneToFive() {
        assertThat(ContactValidator.validateRingPriority(0)).isNotNull()
        assertThat(ContactValidator.validateRingPriority(6)).isNotNull()
        assertThat(ContactValidator.validateRingPriority(3)).isNull()
    }

    @Test
    fun normalizePhone_stripsSpaces() {
        assertThat(ContactValidator.normalizePhone("987 654 3210")).isEqualTo("9876543210")
    }
}
