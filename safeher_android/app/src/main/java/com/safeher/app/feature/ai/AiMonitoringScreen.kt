package com.safeher.app.feature.ai

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.core.designsystem.SafeHerLightPink
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.components.PinkWaveform
import com.safeher.app.core.designsystem.components.SafeHerCard
import com.safeher.app.core.designsystem.components.SafeHerStatusBadge
import com.safeher.app.feature.ai.components.AiConfidenceGauge
import com.safeher.app.feature.ai.components.AiMetricTile
import com.safeher.app.feature.ai.components.AiToggleCard
import com.safeher.app.feature.ai.components.LoadingAi
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.SafeHerScreenHeader
import com.safeher.app.services.ai.AiFeatureFlags
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
        containerColor = MaterialTheme.colorScheme.background,
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState()),
        ) {
            SafeHerScreenHeader(
                title = stringResource(R.string.ai_monitor_title),
                actionIcon = SafeHerIcons.Settings,
                onActionClick = onNavigateToSettings,
                actionContentDescription = stringResource(R.string.ai_settings),
            )

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
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                SafeHerCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .clip(CircleShape)
                                .background(SafeHerLightPink),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(
                                imageVector = SafeHerIcons.Microphone,
                                contentDescription = null,
                                tint = SafeHerPrimary,
                                modifier = Modifier.size(30.dp),
                            )
                        }
                        Text(
                            text = if (uiState.isMonitoring) {
                                stringResource(R.string.ai_listening_title)
                            } else {
                                stringResource(R.string.ai_not_listening_title)
                            },
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            text = stringResource(R.string.home_ai_voice_subtitle),
                            style = MaterialTheme.typography.bodySmall,
                            color = SafeHerTextSecondary,
                        )
                        SafeHerStatusBadge(
                            text = if (uiState.isMonitoring) {
                                stringResource(R.string.status_active)
                            } else {
                                stringResource(R.string.status_inactive)
                            },
                            isActive = uiState.isMonitoring,
                        )
                        PinkWaveform(
                            isActive = uiState.isMonitoring,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(56.dp),
                        )
                    }
                }

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
                        )
                    }
                }

                val confidenceValue = uiState.rollingConfidence
                    ?: uiState.confidence?.totalScore
                AiConfidenceGauge(
                    confidencePercent = confidenceValue,
                    riskLabel = uiState.riskLevelLabel,
                    isLoading = uiState.isLoadingConfidence,
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    AiMetricTile(
                        label = stringResource(R.string.ai_metric_volume),
                        value = volumeLabel(uiState),
                        modifier = Modifier.weight(1f),
                    )
                    AiMetricTile(
                        label = stringResource(R.string.ai_metric_frequency),
                        value = frequencyLabel(uiState),
                        modifier = Modifier.weight(1f),
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    AiMetricTile(
                        label = stringResource(R.string.ai_metric_duration),
                        value = durationLabel(uiState),
                        modifier = Modifier.weight(1f),
                    )
                    AiMetricTile(
                        label = stringResource(R.string.ai_metric_risk),
                        value = uiState.riskLevelLabel ?: stringResource(R.string.ai_unavailable),
                        modifier = Modifier.weight(1f),
                    )
                }

                if (uiState.error != null && uiState.confidence == null) {
                    ErrorView(
                        message = uiState.error.orEmpty(),
                        errorType = ErrorType.GENERIC,
                        onRetry = viewModel::retry,
                    )
                }

                if (AiFeatureFlags.MOVEMENT_AI_ENABLED.not()) {
                    Text(
                        text = stringResource(R.string.ai_movement_coming_soon),
                        style = MaterialTheme.typography.bodySmall,
                        color = SafeHerTextSecondary,
                    )
                }
            }
        }
    }
}

@Composable
private fun volumeLabel(uiState: AiMonitoringUiState): String {
    val assessment = uiState.riskAssessment
    if (assessment != null) {
        return if (assessment.volumeSpike) {
            stringResource(R.string.ai_level_high)
        } else {
            stringResource(R.string.ai_level_normal)
        }
    }
    return if (uiState.audioLevel > 0.6f) {
        stringResource(R.string.ai_level_high)
    } else if (uiState.audioLevel > 0.2f) {
        stringResource(R.string.ai_level_normal)
    } else {
        stringResource(R.string.ai_unavailable)
    }
}

@Composable
private fun frequencyLabel(uiState: AiMonitoringUiState): String {
    val assessment = uiState.riskAssessment
    if (assessment != null) {
        return if (assessment.frequencyAbnormal) {
            stringResource(R.string.ai_level_abnormal)
        } else {
            stringResource(R.string.ai_level_normal)
        }
    }
    return stringResource(R.string.ai_unavailable)
}

@Composable
private fun durationLabel(uiState: AiMonitoringUiState): String {
    val seconds = uiState.riskAssessment?.durationSeconds
    return if (seconds != null && seconds > 0) {
        stringResource(R.string.ai_duration_seconds, seconds.toInt())
    } else {
        stringResource(R.string.ai_unavailable)
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
