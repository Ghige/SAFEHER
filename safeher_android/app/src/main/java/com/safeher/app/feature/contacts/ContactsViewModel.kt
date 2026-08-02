package com.safeher.app.feature.contacts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.domain.model.EmergencyContact
import com.safeher.app.domain.repository.ContactsRepository
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

@HiltViewModel
class ContactsViewModel @Inject constructor(
    private val contactsRepository: ContactsRepository,
    private val networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ContactsUiState())
    val uiState: StateFlow<ContactsUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<ContactsEvent>()
    val events: SharedFlow<ContactsEvent> = _events.asSharedFlow()

    init {
        observeNetwork()
        loadContacts()
    }

    fun loadContacts() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            fetchContacts(isRefresh = false)
        }
    }

    fun refreshContacts() {
        viewModelScope.launch {
            _uiState.update { it.copy(isRefreshing = true, error = null) }
            fetchContacts(isRefresh = true)
        }
    }

    private suspend fun fetchContacts(isRefresh: Boolean) {
        val result = contactsRepository.getContacts()
        result.fold(
            onSuccess = { contacts ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isRefreshing = false,
                        contacts = contacts,
                        error = null,
                    )
                }
            },
            onFailure = { error ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = error.message,
                    )
                }
            },
        )
    }

    fun onAddContactClick() {
        if (!_uiState.value.canAddContact) {
            _uiState.update {
                it.copy(snackbarMessage = "Maximum 5 emergency contacts allowed")
            }
            return
        }
        viewModelScope.launch {
            _events.emit(ContactsEvent.NavigateToAddContact)
        }
    }

    fun onDeleteClick(contact: EmergencyContact) {
        _uiState.update { it.copy(contactToDelete = contact) }
    }

    fun dismissDeleteDialog() {
        _uiState.update { it.copy(contactToDelete = null) }
    }

    fun confirmDelete() {
        val contact = _uiState.value.contactToDelete ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isDeleting = true) }
            val result = contactsRepository.deleteContact(contact.id)
            result.fold(
                onSuccess = {
                    _uiState.update {
                        it.copy(
                            isDeleting = false,
                            contactToDelete = null,
                            contacts = it.contacts.filter { c -> c.id != contact.id },
                        )
                    }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(
                            isDeleting = false,
                            contactToDelete = null,
                            snackbarMessage = error.message,
                        )
                    }
                },
            )
        }
    }

    fun clearSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }
}
