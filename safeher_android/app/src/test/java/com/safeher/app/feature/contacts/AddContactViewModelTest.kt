package com.safeher.app.feature.contacts

import app.cash.turbine.test
import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.repository.ContactsRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AddContactViewModelTest {

    private val contactsRepository: ContactsRepository = mockk()
    private lateinit var viewModel: AddContactViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        viewModel = AddContactViewModel(contactsRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun saveContact_withInvalidPhone_setsPhoneError() = runTest {
        viewModel.onNameChange("Mom")
        viewModel.onPhoneChange("123")
        viewModel.onRelationshipChange("Mother")
        viewModel.saveContact()

        assertEquals("Enter a valid 10-digit phone number", viewModel.uiState.value.phoneError)
        coVerify(exactly = 0) { contactsRepository.addContact(any(), any(), any(), any()) }
    }

    @Test
    fun saveContact_success_navigatesBack() = runTest {
        coEvery {
            contactsRepository.addContact(any(), any(), any(), any())
        } returns Result.success(
            EmergencyContact("id", "Mom", "9876543210", "Mother", 1, true),
        )

        viewModel.onNameChange("Mom")
        viewModel.onPhoneChange("9876543210")
        viewModel.onRelationshipChange("Mother")
        viewModel.onRingPriorityChange(2)

        viewModel.events.test {
            viewModel.saveContact()
            assertEquals(AddContactEvent.NavigateBack, awaitItem())
        }

        coVerify {
            contactsRepository.addContact("Mom", "9876543210", "Mother", 2)
        }
    }

    @Test
    fun saveContact_maxContactsError_fromBackend() = runTest {
        coEvery {
            contactsRepository.addContact(any(), any(), any(), any())
        } returns Result.failure(Exception("Maximum 5 emergency contacts allowed"))

        viewModel.onNameChange("Mom")
        viewModel.onPhoneChange("9876543210")
        viewModel.onRelationshipChange("Mother")
        viewModel.saveContact()

        assertEquals(
            "Maximum 5 emergency contacts allowed",
            viewModel.uiState.value.error,
        )
    }
}
