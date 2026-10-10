package com.safeher.app.feature.sos

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.sos.components.LoadingSOS
import com.safeher.app.feature.sos.components.SosGradientBackground
import com.safeher.app.feature.sos.components.SosLocationWarningBanner
import kotlinx.coroutines.flow.collectLatest

@Composable
fun CountdownScreen(
    onNavigateBack: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SOSViewModel = rememberSosViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.startCountdown()
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                SOSEvent.NavigateBack -> onNavigateBack()
                else -> Unit
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
        containerColor = MaterialTheme.colorScheme.surface,
    ) { padding ->
        SosGradientBackground {
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

                if (uiState.showLocationWarning) {
                    SosLocationWarningBanner(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    )
                }

                when {
                    uiState.isTriggering -> LoadingSOS()
                    uiState.countdownSeconds != null -> EmergencyCountdown(
                        secondsRemaining = uiState.countdownSeconds!!,
                        totalSeconds = SOSViewModel.COUNTDOWN_SECONDS,
                        onCancel = viewModel::cancelCountdown,
                    )
                    else -> LoadingSOS()
                }
            }
        }
    }
}
