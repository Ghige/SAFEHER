package com.safeher.app.domain.repository

import com.safeher.app.domain.model.EmergencyContact

interface ContactsRepository {

    suspend fun getContacts(): Result<List<EmergencyContact>>

    suspend fun addContact(
        name: String,
        phoneNumber: String,
        relationship: String,
        ringPriority: Int,
    ): Result<EmergencyContact>

    suspend fun deleteContact(contactId: String): Result<Unit>
}
