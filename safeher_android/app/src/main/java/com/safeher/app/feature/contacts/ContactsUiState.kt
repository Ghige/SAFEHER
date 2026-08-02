package com.safeher.app.feature.contacts

import com.safeher.app.domain.model.EmergencyContact

data class ContactsUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val contacts: List<EmergencyContact> = emptyList(),
    val error: String? = null,
    val isOffline: Boolean = false,
    val contactToDelete: EmergencyContact? = null,
    val isDeleting: Boolean = false,
    val snackbarMessage: String? = null,
) {
    val canAddContact: Boolean get() = contacts.size < MAX_CONTACTS

    companion object {
        const val MAX_CONTACTS = 5
    }
}
