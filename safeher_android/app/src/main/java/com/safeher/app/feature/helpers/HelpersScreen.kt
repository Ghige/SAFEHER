package com.safeher.app.feature.helpers

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.helpers.components.EmptyHelpersView
import com.safeher.app.feature.helpers.components.HelperCard
import com.safeher.app.feature.helpers.components.LoadingHelpers
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import kotlinx.coroutines.flow.collectLatest

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpersScreen(
    onNavigateToProfile: (String) -> Unit,
    onNavigateToBlocked: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: HelpersViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                is HelpersEvent.NavigateToProfile -> onNavigateToProfile(event.helperId)
                HelpersEvent.NavigateToBlocked -> onNavigateToBlocked()
            }
        }
    }

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSnackbar()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            if (uiState.helpers.isNotEmpty()) {
                snackbarHostState.showSnackbar(it)
                viewModel.clearError()
            }
        }
    }

    uiState.helperToRespond?.let {
        HelperResponseDialog(
            onAccept = { viewModel.confirmRespond(HelperResponseAction.ACCEPT) },
            onDecline = { viewModel.confirmRespond(HelperResponseAction.DECLINE) },
            onDismiss = viewModel::dismissRespondDialog,
            isLoading = uiState.isResponding,
        )
    }

    uiState.helperToBlock?.let {
        HelperBlockDialog(
            onConfirm = viewModel::confirmBlock,
            onDismiss = viewModel::dismissBlockDialog,
            isLoading = uiState.isBlocking,
        )
    }

    Scaffold(
        modifier = Modifier.padding(contentPadding),
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.padding(innerPadding)) {
            Column {
                if (uiState.isOffline) {
                    Surface(color = MaterialTheme.colorScheme.errorContainer) {
                        OfflineBanner()
                    }
                }

                when {
                    uiState.isLoading -> LoadingHelpers()
                    uiState.error != null && uiState.helpers.isEmpty() -> {
                        ErrorView(
                            message = uiState.error.orEmpty(),
                            onRetry = viewModel::loadHelpers,
                            errorType = if (uiState.isOffline) ErrorType.OFFLINE else ErrorType.NETWORK,
                        )
                    }
                    uiState.helpers.isEmpty() -> {
                        EmptyHelpersView(hasActiveAlert = uiState.activeAlertId != null)
                    }
                    else -> {
                        PullToRefreshBox(
                            isRefreshing = uiState.isRefreshing,
                            onRefresh = viewModel::refreshHelpers,
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            LazyColumn(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                item {
                                    OutlinedButton(
                                        onClick = viewModel::navigateToBlocked,
                                        modifier = Modifier.fillMaxWidth(),
                                    ) {
                                        Text(
                                            stringResource(
                                                R.string.helpers_view_blocked,
                                                uiState.blockedHelpers.size,
                                            ),
                                        )
                                    }
                                }
                                items(uiState.helpers, key = { it.id }) { helper ->
                                    HelperCard(
                                        helper = helper,
                                        onClick = { viewModel.onHelperClick(helper) },
                                        onRespond = { viewModel.onRespondClick(helper) },
                                        onBlock = { viewModel.onBlockClick(helper) },
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
