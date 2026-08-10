package com.safeher.app.feature.ai.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.domain.model.AiConfidenceResult
import com.safeher.app.services.ai.AiFeatureFlags

@Composable
fun ConfidenceCard(
    confidence: AiConfidenceResult?,
    isLoading: Boolean,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = stringResource(R.string.ai_confidence_title),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            if (isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            if (confidence != null) {
                Text(
                    text = stringResource(R.string.ai_overall_confidence, confidence.totalScore),
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = stringResource(R.string.ai_audio_confidence, confidence.audioScore),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    if (AiFeatureFlags.MOVEMENT_AI_ENABLED) {
                        Text(
                            text = stringResource(R.string.ai_movement_confidence, confidence.movementScore),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                DetectionStatusChip(action = confidence.action)
            } else {
                Text(
                    text = stringResource(R.string.ai_confidence_waiting),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.8f),
                )
            }
        }
    }
}
