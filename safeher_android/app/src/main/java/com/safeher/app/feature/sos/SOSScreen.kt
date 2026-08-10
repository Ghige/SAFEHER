package com.safeher.app.feature.sos

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.sos.components.LoadingSOS
import com.safeher.app.feature.sos.components.SOSButton
import com.safeher.app.feature.sos.components.SosAlertWarningBanner
import com.safeher.app.feature.home.components.SafeHerScreenHeader
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.feature.sos.components.SosPreflightChecklist
import kotlinx.coroutines.flow.collectLatest
import timber.log.Timber

@Composable
fun SOSScreen(
    onNavigateToCountdown: () -> Unit,
    onNavigateToActive: () -> Unit,
    onNavigateToHistory: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SOSViewModel = rememberSosViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.activeAlert?.id, uiState.isLoading) {
        Timber.d(
            "SOSScreen: alertId=%s isLoading=%s ongoing=%s",
            uiState.activeAlert?.id,
            uiState.isLoading,
            uiState.activeAlert?.isOngoing,
        )
    }

    LaunchedEffect(Unit) {
        viewModel.refreshPreflight()
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                SOSEvent.NavigateToCountdown -> onNavigateToCountdown()
                SOSEvent.NavigateToActive -> onNavigateToActive()
                SOSEvent.NavigateToHistory -> onNavigateToHistory()
                SOSEvent.NavigateBack -> Unit
            }
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { message ->
            snackbarHostState.showSnackbar(message)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(padding),
        ) {
            SafeHerScreenHeader(
                title = stringResource(R.string.nav_alerts),
                actionIcon = SafeHerIcons.History,
                onActionClick = viewModel::navigateToHistory,
                actionContentDescription = stringResource(R.string.sos_view_history),
            )
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            when {
                uiState.isLoading -> LoadingSOS()
                else -> SOSContent(
                    uiState = uiState,
                    onSosClick = viewModel::onSosButtonClick,
                    onHistoryClick = viewModel::navigateToHistory,
                    onOpenLocationSettings = viewModel::openLocationSettings,
                    onOpenAppSettings = viewModel::openAppSettings,
                    onOpenBatterySettings = viewModel::openBatterySettings,
                )
            }
        }
    }
}

@Composable
private fun SOSContent(
    uiState: SOSUiState,
    onSosClick: () -> Unit,
    onHistoryClick: () -> Unit,
    onOpenLocationSettings: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onOpenBatterySettings: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        uiState.preflight?.let { preflight ->
            SosPreflightChecklist(
                preflight = preflight,
                onOpenLocationSettings = onOpenLocationSettings,
                onOpenAppSettings = onOpenAppSettings,
                onOpenBatterySettings = onOpenBatterySettings,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(modifier = Modifier.height(20.dp))
        }

        if (uiState.hasPendingSos && uiState.queuedMessage != null) {
            SosAlertWarningBanner(message = uiState.queuedMessage)
            Spacer(modifier = Modifier.height(12.dp))
        }

        Column(
            modifier = Modifier.weight(1f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = stringResource(R.string.sos_title),
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = if (uiState.activeAlert?.isOngoing == true) {
                    stringResource(R.string.sos_active_hint)
                } else {
                    stringResource(R.string.sos_subtitle)
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(40.dp))

            if (uiState.isTriggering) {
                LoadingSOS(message = stringResource(R.string.sos_triggering))
            } else {
                SOSButton(
                    onClick = onSosClick,
                    enabled = true,
                )
            }
        }

        OutlinedButton(
            onClick = onHistoryClick,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.sos_view_history))
        }
    }
}
