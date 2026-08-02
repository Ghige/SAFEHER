package com.safeher.app.feature.contacts

import app.cash.turbine.test
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.repository.ContactsRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ContactsViewModelTest {

    private val contactsRepository: ContactsRepository = mockk()
    private val networkMonitor: NetworkMonitor = mockk()
    private lateinit var viewModel: ContactsViewModel

    private val sampleContacts = listOf(
        EmergencyContact(
            id = "uuid-1",
            name = "Mom",
            phoneNumber = "9876543210",
            relationship = "Mother",
            ringPriority = 1,
            isActive = true,
        ),
    )

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        every { networkMonitor.isOnline } returns flowOf(true)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun loadContacts_success_updatesList() = runTest {
        coEvery { contactsRepository.getContacts() } returns Result.success(sampleContacts)
        viewModel = ContactsViewModel(contactsRepository, networkMonitor)

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals(sampleContacts, viewModel.uiState.value.contacts)
    }

    @Test
    fun loadContacts_failure_setsError() = runTest {
        coEvery { contactsRepository.getContacts() } returns Result.failure(Exception("Network error"))
        viewModel = ContactsViewModel(contactsRepository, networkMonitor)

        assertEquals("Network error", viewModel.uiState.value.error)
        assertTrue(viewModel.uiState.value.contacts.isEmpty())
    }

    @Test
    fun confirmDelete_removesContactFromList() = runTest {
        coEvery { contactsRepository.getContacts() } returns Result.success(sampleContacts)
        coEvery { contactsRepository.deleteContact("uuid-1") } returns Result.success(Unit)
        viewModel = ContactsViewModel(contactsRepository, networkMonitor)

        viewModel.onDeleteClick(sampleContacts.first())
        viewModel.confirmDelete()

        assertNull(viewModel.uiState.value.contactToDelete)
        assertTrue(viewModel.uiState.value.contacts.isEmpty())
        coVerify { contactsRepository.deleteContact("uuid-1") }
    }

    @Test
    fun onAddContactClick_atMaxContacts_showsSnackbar() = runTest {
        val fiveContacts = (1..5).map { index ->
            sampleContacts.first().copy(id = "uuid-$index", name = "Contact $index")
        }
        coEvery { contactsRepository.getContacts() } returns Result.success(fiveContacts)
        viewModel = ContactsViewModel(contactsRepository, networkMonitor)

        viewModel.onAddContactClick()

        assertEquals(
            "Maximum 5 emergency contacts allowed",
            viewModel.uiState.value.snackbarMessage,
        )
        assertFalse(viewModel.uiState.value.canAddContact)
    }

    @Test
    fun onAddContactClick_underLimit_emitsNavigationEvent() = runTest {
        coEvery { contactsRepository.getContacts() } returns Result.success(sampleContacts)
        viewModel = ContactsViewModel(contactsRepository, networkMonitor)

        viewModel.events.test {
            viewModel.onAddContactClick()
            assertEquals(ContactsEvent.NavigateToAddContact, awaitItem())
        }
    }
}
