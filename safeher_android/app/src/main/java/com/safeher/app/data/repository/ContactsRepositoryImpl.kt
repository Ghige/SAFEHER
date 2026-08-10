package com.safeher.app.data.repository

import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.core.network.ContactsApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.ContactDto
import com.safeher.app.data.remote.dto.CreateContactRequestDto
import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.repository.ContactsRepository
import com.squareup.moshi.Moshi
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ContactsRepositoryImpl @Inject constructor(
    private val api: ContactsApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : ContactsRepository {

    override suspend fun getContacts(): Result<List<EmergencyContact>> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.getContacts().map { it.toDomain() }
        }

    override suspend fun addContact(
        name: String,
        phoneNumber: String,
        relationship: String,
        ringPriority: Int,
    ): Result<EmergencyContact> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.createContact(
                CreateContactRequestDto(
                    name = name.trim(),
                    phone_number = phoneNumber.trim(),
                    relationship = relationship.trim(),
                    ring_priority = ringPriority,
                ),
            ).toDomain()
        }

    override suspend fun deleteContact(contactId: String): Result<Unit> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.deleteContact(contactId)
        }

    private fun ContactDto.toDomain() = EmergencyContact(
        id = id,
        name = name,
        phoneNumber = phone_number,
        relationship = relationship,
        ringPriority = ring_priority,
        isActive = is_active,
    )
}
