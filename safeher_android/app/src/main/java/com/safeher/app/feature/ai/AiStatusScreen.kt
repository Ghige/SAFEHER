package com.safeher.app.feature.ai

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.ai.components.ConfidenceCard
import com.safeher.app.feature.ai.components.DetectionStatusChip
import com.safeher.app.feature.ai.components.MovementIndicator
import com.safeher.app.feature.ai.components.AudioLevelIndicator
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.domain.model.AiAction

@Composable
fun AiStatusScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: AiMonitoringViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            Text(
                text = stringResource(R.string.ai_status_title),
                style = MaterialTheme.typography.headlineSmall,
            )

            StatusRow(
                label = stringResource(R.string.ai_status_monitoring),
                value = if (uiState.isMonitoring) {
                    stringResource(R.string.ai_monitoring_active)
                } else {
                    stringResource(R.string.ai_monitoring_inactive)
                },
            )

            StatusRow(
                label = stringResource(R.string.ai_status_models),
                value = if (uiState.modelsAvailable) {
                    stringResource(R.string.ai_status_models_ready)
                } else {
                    stringResource(R.string.ai_status_models_missing)
                },
            )

            StatusRow(
                label = stringResource(R.string.ai_status_foreground),
                value = if (uiState.isAppInForeground) {
                    stringResource(R.string.ai_status_foreground_active)
                } else {
                    stringResource(R.string.ai_status_foreground_paused)
                },
            )

            AudioLevelIndicator(
                level = uiState.audioLevel,
                isActive = uiState.isMonitoring,
                modifier = Modifier.padding(vertical = 8.dp),
            )

            MovementIndicator(
                level = uiState.movementLevel,
                isActive = uiState.isMonitoring,
            )

            ConfidenceCard(
                confidence = uiState.confidence,
                isLoading = uiState.isLoadingConfidence,
            )

            uiState.confidence?.action?.let { action ->
                DetectionStatusChip(action = action)
            } ?: DetectionStatusChip(action = AiAction.NOTHING)
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(top = 2.dp),
        )
    }
}
