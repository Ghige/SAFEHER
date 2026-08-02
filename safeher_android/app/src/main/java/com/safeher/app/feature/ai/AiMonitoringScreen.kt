package com.safeher.app.feature.ai

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.ai.components.AiToggleCard
import com.safeher.app.feature.ai.components.AudioLevelIndicator
import com.safeher.app.feature.ai.components.ConfidenceCard
import com.safeher.app.feature.ai.components.ListeningAnimation
import com.safeher.app.feature.ai.components.LoadingAi
import com.safeher.app.feature.ai.components.MovementIndicator
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.services.AudioPermissionStatus
import kotlinx.coroutines.flow.collectLatest

@Composable
fun AiMonitoringScreen(
    onNavigateToSosCountdown: () -> Unit,
    onNavigateToActiveAlert: () -> Unit,
    onNavigateToStatus: () -> Unit,
    onNavigateToSettings: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: AiMonitoringViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val lifecycleOwner = LocalLifecycleOwner.current

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        viewModel.onPermissionResult(
            granted = granted,
            shouldShowRationale = !granted,
        )
        if (granted) {
            viewModel.onToggleMonitoring(true)
        }
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> viewModel.setAppInForeground(true)
                Lifecycle.Event.ON_STOP -> viewModel.setAppInForeground(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                AiMonitoringEvent.NavigateToSosCountdown -> onNavigateToSosCountdown()
                AiMonitoringEvent.NavigateToActiveAlert -> onNavigateToActiveAlert()
                AiMonitoringEvent.NavigateToStatus -> onNavigateToStatus()
                AiMonitoringEvent.NavigateToSettings -> onNavigateToSettings()
                AiMonitoringEvent.RequestAudioPermission ->
                    permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSnackbar()
        }
    }

    Scaffold(
        modifier = Modifier.padding(contentPadding),
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState()),
        ) {
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            if (uiState.isLoading) {
                LoadingAi()
                return@Column
            }

            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                AiToggleCard(
                    enabled = uiState.monitoringEnabled,
                    isMonitoring = uiState.isMonitoring,
                    onToggle = viewModel::onToggleMonitoring,
                )

                if (uiState.audioPermissionStatus != AudioPermissionStatus.GRANTED) {
                    AudioPermissionBanner(
                        status = uiState.audioPermissionStatus,
                        onRequestPermission = {
                            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        },
                        onOpenSettings = viewModel::onOpenAppSettings,
                    )
                }

                if (!uiState.modelsAvailable) {
                    Surface(
                        color = MaterialTheme.colorScheme.tertiaryContainer,
                        shape = MaterialTheme.shapes.medium,
                    ) {
                        Text(
                            text = stringResource(R.string.ai_models_missing),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(12.dp),
                            color = MaterialTheme.colorScheme.onTertiaryContainer,
                        )
                    }
                }

                Box(contentAlignment = Alignment.Center) {
                    ListeningAnimation(isListening = uiState.isMonitoring)
                    AudioLevelIndicator(
                        level = uiState.audioLevel,
                        isActive = uiState.isMonitoring,
                    )
                }

                MovementIndicator(
                    level = uiState.movementLevel,
                    isActive = uiState.isMonitoring,
                )

                ConfidenceCard(
                    confidence = uiState.confidence,
                    isLoading = uiState.isLoadingConfidence,
                )

                if (uiState.error != null && uiState.confidence == null) {
                    ErrorView(
                        message = uiState.error.orEmpty(),
                        errorType = ErrorType.GENERIC,
                        onRetry = viewModel::retry,
                    )
                } else if (uiState.error != null) {
                    Text(
                        text = uiState.error.orEmpty(),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = onNavigateToStatus,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(stringResource(R.string.ai_view_status))
                    }
                    OutlinedButton(
                        onClick = onNavigateToSettings,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(stringResource(R.string.ai_settings))
                    }
                }
            }
        }
    }
}

@Composable
private fun AudioPermissionBanner(
    status: AudioPermissionStatus,
    onRequestPermission: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = stringResource(R.string.ai_audio_permission_required),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            if (status == AudioPermissionStatus.PERMANENTLY_DENIED) {
                Button(onClick = onOpenSettings) {
                    Text(stringResource(R.string.ai_open_settings))
                }
            } else {
                Button(onClick = onRequestPermission) {
                    Text(stringResource(R.string.ai_grant_permission))
                }
            }
        }
    }
}
