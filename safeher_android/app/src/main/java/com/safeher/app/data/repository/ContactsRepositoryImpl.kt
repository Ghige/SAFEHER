package com.safeher.app.data.repository

import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.ContactsApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.ContactDto
import com.safeher.app.data.remote.dto.CreateContactRequestDto
import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.repository.ContactsRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ContactsRepositoryImpl @Inject constructor(
    private val api: ContactsApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : ContactsRepository {

    override suspend fun getContacts(): Result<List<EmergencyContact>> {
        return apiCall {
            api.getContacts().map { it.toDomain() }
        }
    }

    override suspend fun addContact(
        name: String,
        phoneNumber: String,
        relationship: String,
        ringPriority: Int,
    ): Result<EmergencyContact> {
        return apiCall {
            api.createContact(
                CreateContactRequestDto(
                    name = name.trim(),
                    phone_number = phoneNumber.trim(),
                    relationship = relationship.trim(),
                    ring_priority = ringPriority,
                ),
            ).toDomain()
        }
    }

    override suspend fun deleteContact(contactId: String): Result<Unit> {
        return apiCall {
            api.deleteContact(contactId)
        }
    }

    private suspend inline fun <T> apiCall(block: () -> T): Result<T> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                Result.failure(Exception("You are offline. Connect to the internet and try again."))
            } else {
                Result.success(block())
            }
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
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
