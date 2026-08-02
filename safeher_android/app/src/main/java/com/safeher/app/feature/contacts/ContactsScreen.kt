package com.safeher.app.feature.contacts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavBackStackEntry
import com.safeher.app.feature.contacts.components.AddContactButton
import com.safeher.app.feature.contacts.components.ContactCard
import com.safeher.app.feature.contacts.components.LoadingContacts
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import kotlinx.coroutines.flow.collectLatest

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContactsScreen(
    onNavigateToAddContact: () -> Unit,
    backStackEntry: NavBackStackEntry,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: ContactsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val shouldRefresh by backStackEntry.savedStateHandle
        .getStateFlow("refresh_contacts", false)
        .collectAsStateWithLifecycle()

    LaunchedEffect(shouldRefresh) {
        if (shouldRefresh) {
            viewModel.refreshContacts()
            backStackEntry.savedStateHandle["refresh_contacts"] = false
        }
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                ContactsEvent.NavigateToAddContact -> onNavigateToAddContact()
            }
        }
    }

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let { message ->
            snackbarHostState.showSnackbar(message)
            viewModel.clearSnackbar()
        }
    }

    uiState.contactToDelete?.let { contact ->
        DeleteContactDialog(
            contact = contact,
            isDeleting = uiState.isDeleting,
            onConfirm = viewModel::confirmDelete,
            onDismiss = viewModel::dismissDeleteDialog,
        )
    }

    Scaffold(
        modifier = Modifier.padding(contentPadding),
        snackbarHost = { SnackbarHost(snackbarHostState) },
        floatingActionButton = {
            if (!uiState.isLoading && uiState.error == null) {
                AddContactButton(
                    onClick = viewModel::onAddContactClick,
                    enabled = uiState.canAddContact,
                )
            }
        },
    ) { innerPadding ->
        Box(modifier = Modifier.padding(innerPadding)) {
            ColumnWithOfflineBanner(isOffline = uiState.isOffline) {
                when {
                    uiState.isLoading -> LoadingContacts()
                    uiState.error != null && uiState.contacts.isEmpty() -> {
                        ErrorView(
                            message = uiState.error.orEmpty(),
                            onRetry = viewModel::loadContacts,
                            errorType = when {
                                uiState.isOffline -> ErrorType.OFFLINE
                                uiState.error.orEmpty().contains("offline", ignoreCase = true) -> ErrorType.OFFLINE
                                else -> ErrorType.NETWORK
                            },
                        )
                    }
                    uiState.contacts.isEmpty() -> {
                        PullToRefreshBox(
                            isRefreshing = uiState.isRefreshing,
                            onRefresh = viewModel::refreshContacts,
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            EmptyContactsView()
                        }
                    }
                    else -> {
                        PullToRefreshBox(
                            isRefreshing = uiState.isRefreshing,
                            onRefresh = viewModel::refreshContacts,
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                contentPadding = PaddingValues(16.dp),
                                verticalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                items(
                                    items = uiState.contacts,
                                    key = { it.id },
                                ) { contact ->
                                    ContactCard(
                                        contact = contact,
                                        onDelete = { viewModel.onDeleteClick(contact) },
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ColumnWithOfflineBanner(
    isOffline: Boolean,
    content: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        if (isOffline) {
            Surface(color = MaterialTheme.colorScheme.errorContainer) {
                OfflineBanner()
            }
        }
        Box(modifier = Modifier.weight(1f)) {
            content()
        }
    }
}
