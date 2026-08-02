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
import kotlinx.coroutines.flow.collectLatest

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
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(padding),
        ) {
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
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = stringResource(R.string.sos_title),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
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
        Spacer(modifier = Modifier.height(48.dp))

        if (uiState.isTriggering) {
            LoadingSOS(message = stringResource(R.string.sos_triggering))
        } else {
            SOSButton(
                onClick = onSosClick,
                enabled = !uiState.isOffline,
            )
        }

        Spacer(modifier = Modifier.height(32.dp))
        OutlinedButton(
            onClick = onHistoryClick,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.sos_view_history))
        }
    }
}
