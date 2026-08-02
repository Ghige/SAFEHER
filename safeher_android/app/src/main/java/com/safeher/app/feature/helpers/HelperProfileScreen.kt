package com.safeher.app.feature.helpers

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.helpers.components.AvailabilityChip
import com.safeher.app.feature.helpers.components.DistanceBadge
import com.safeher.app.feature.helpers.components.LoadingHelpers
import com.safeher.app.feature.helpers.components.RespondButton
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner

@Composable
fun HelperProfileScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: HelperProfileViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSnackbar()
        }
    }

    if (uiState.showResponseDialog) {
        HelperResponseDialog(
            onAccept = { viewModel.confirmRespond(HelperResponseAction.ACCEPT) },
            onDecline = { viewModel.confirmRespond(HelperResponseAction.DECLINE) },
            onDismiss = viewModel::dismissResponseDialog,
            isLoading = uiState.isResponding,
        )
    }

    Scaffold(
        modifier = Modifier.padding(contentPadding),
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
        ) {
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            when {
                uiState.isLoading -> LoadingHelpers()
                uiState.error != null && uiState.helper == null -> {
                    ErrorView(
                        message = uiState.error.orEmpty(),
                        onRetry = viewModel::loadHelper,
                        errorType = if (uiState.isOffline) ErrorType.OFFLINE else ErrorType.NETWORK,
                    )
                }
                uiState.helper != null -> {
                    val helper = uiState.helper!!
                    Text(
                        text = helper.displayName,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = stringResource(R.string.helpers_notified_at, helper.notifiedAt),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    androidx.compose.foundation.layout.Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        DistanceBadge(distanceLabel = helper.distanceLabel)
                        AvailabilityChip(
                            status = helper.status,
                            label = helper.availabilityLabel,
                        )
                    }
                    if (helper.identityRevealed && helper.phoneNumber != null) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = stringResource(R.string.field_phone),
                            style = MaterialTheme.typography.labelMedium,
                        )
                        Text(
                            text = helper.phoneNumber,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                    Spacer(modifier = Modifier.height(24.dp))
                    if (helper.canRespond && !helper.isBlocked) {
                        RespondButton(
                            onAccept = viewModel::showResponseDialog,
                            onDecline = { viewModel.confirmRespond(HelperResponseAction.DECLINE) },
                            enabled = !uiState.isResponding && !uiState.isBlocking,
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                    if (!helper.isBlocked) {
                        Button(
                            onClick = viewModel::blockHelper,
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !uiState.isBlocking,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error,
                            ),
                        ) {
                            Text(stringResource(R.string.helpers_block_confirm))
                        }
                    }
                }
            }
        }
    }
}
