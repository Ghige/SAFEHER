package com.safeher.app.feature.contacts

sealed interface ContactsEvent {
    data object NavigateToAddContact : ContactsEvent
}
