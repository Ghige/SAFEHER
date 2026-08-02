package com.safeher.app.data.repository

import com.safeher.app.core.network.ContactsApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.ContactDto
import com.safeher.app.data.remote.dto.CreateContactRequestDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ContactsRepositoryImplTest {

    private val api: ContactsApi = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: ContactsRepositoryImpl

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        repository = ContactsRepositoryImpl(api, networkMonitor, moshi)
    }

    @Test
    fun getContacts_mapsDtoToDomain() = runTest {
        coEvery { api.getContacts() } returns listOf(
            ContactDto(
                id = "uuid-1",
                name = "Mom",
                phone_number = "9876543210",
                relationship = "Mother",
                ring_priority = 1,
                is_active = true,
            ),
        )

        val result = repository.getContacts()

        assertTrue(result.isSuccess)
        val contact = result.getOrNull()!!.first()
        assertEquals("uuid-1", contact.id)
        assertEquals("Mom", contact.name)
        assertEquals("9876543210", contact.phoneNumber)
    }

    @Test
    fun addContact_callsApiWithCorrectBody() = runTest {
        coEvery { api.createContact(any()) } returns ContactDto(
            id = "uuid-2",
            name = "Dad",
            phone_number = "9123456789",
            relationship = "Father",
            ring_priority = 2,
        )

        val result = repository.addContact("Dad", "9123456789", "Father", 2)

        assertTrue(result.isSuccess)
        coVerify {
            api.createContact(
                CreateContactRequestDto(
                    name = "Dad",
                    phone_number = "9123456789",
                    relationship = "Father",
                    ring_priority = 2,
                ),
            )
        }
    }

    @Test
    fun deleteContact_usesUuidFromBackend() = runTest {
        coEvery { api.deleteContact("550e8400-e29b-41d4-a716-446655440000") } returns Unit

        val result = repository.deleteContact("550e8400-e29b-41d4-a716-446655440000")

        assertTrue(result.isSuccess)
        coVerify { api.deleteContact("550e8400-e29b-41d4-a716-446655440000") }
    }

    @Test
    fun getContacts_offline_returnsFailure() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.getContacts()

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("offline", ignoreCase = true) == true)
    }
}
