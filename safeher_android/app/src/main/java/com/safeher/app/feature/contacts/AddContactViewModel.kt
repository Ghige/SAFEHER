package com.safeher.app.feature.contacts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.domain.repository.ContactsRepository
import com.safeher.app.feature.contacts.util.ContactValidator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AddContactUiState(
    val name: String = "",
    val phone: String = "",
    val relationship: String = "",
    val ringPriority: Int = 1,
    val isLoading: Boolean = false,
    val error: String? = null,
    val nameError: String? = null,
    val phoneError: String? = null,
    val relationshipError: String? = null,
    val priorityError: String? = null,
)

sealed interface AddContactEvent {
    data object NavigateBack : AddContactEvent
}

@HiltViewModel
class AddContactViewModel @Inject constructor(
    private val contactsRepository: ContactsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AddContactUiState())
    val uiState: StateFlow<AddContactUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<AddContactEvent>()
    val events: SharedFlow<AddContactEvent> = _events.asSharedFlow()

    fun onNameChange(value: String) {
        _uiState.update { it.copy(name = value, nameError = null, error = null) }
    }

    fun onPhoneChange(value: String) {
        _uiState.update { it.copy(phone = value, phoneError = null, error = null) }
    }

    fun onRelationshipChange(value: String) {
        _uiState.update { it.copy(relationship = value, relationshipError = null, error = null) }
    }

    fun onRingPriorityChange(value: Int) {
        _uiState.update { it.copy(ringPriority = value, priorityError = null, error = null) }
    }

    fun saveContact() {
        val name = _uiState.value.name
        val phone = ContactValidator.normalizePhone(_uiState.value.phone)
        val relationship = _uiState.value.relationship
        val priority = _uiState.value.ringPriority

        val nameError = ContactValidator.validateName(name)
        val phoneError = ContactValidator.validatePhone(phone)
        val relationshipError = ContactValidator.validateRelationship(relationship)
        val priorityError = ContactValidator.validateRingPriority(priority)

        if (nameError != null || phoneError != null || relationshipError != null || priorityError != null) {
            _uiState.update {
                it.copy(
                    nameError = nameError,
                    phoneError = phoneError,
                    relationshipError = relationshipError,
                    priorityError = priorityError,
                )
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = contactsRepository.addContact(
                name = name,
                phoneNumber = phone,
                relationship = relationship,
                ringPriority = priority,
            )
            _uiState.update { it.copy(isLoading = false) }
            result.fold(
                onSuccess = { _events.emit(AddContactEvent.NavigateBack) },
                onFailure = { error ->
                    _uiState.update { it.copy(error = error.message) }
                },
            )
        }
    }
}
