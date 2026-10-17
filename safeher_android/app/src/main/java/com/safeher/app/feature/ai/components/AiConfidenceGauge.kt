package com.safeher.app.feature.ai.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerLightPink
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.components.SafeHerCard

@Composable
fun AiConfidenceGauge(
    confidencePercent: Double?,
    riskLabel: String?,
    isLoading: Boolean,
    modifier: Modifier = Modifier,
) {
    SafeHerCard(modifier = modifier.fillMaxWidth()) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = stringResource(R.string.ai_confidence_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Box(
                modifier = Modifier
                    .size(140.dp)
                    .clip(CircleShape)
                    .background(SafeHerLightPink),
                contentAlignment = Alignment.Center,
            ) {
                if (isLoading) {
                    CircularProgressIndicator(color = SafeHerPrimary)
                } else if (confidencePercent != null) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "${confidencePercent.toInt()}%",
                            style = MaterialTheme.typography.headlineMedium,
                            color = SafeHerPrimary,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = stringResource(R.string.ai_confidence_label),
                            style = MaterialTheme.typography.bodySmall,
                            color = SafeHerTextSecondary,
                        )
                    }
                } else {
                    Text(
                        text = stringResource(R.string.ai_confidence_waiting),
                        style = MaterialTheme.typography.bodySmall,
                        color = SafeHerTextSecondary,
                    )
                }
            }
            if (riskLabel != null) {
                Text(
                    text = stringResource(R.string.ai_risk_level_value, riskLabel),
                    style = MaterialTheme.typography.bodyMedium,
                    color = SafeHerPrimary,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

@Composable
fun AiMetricTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    SafeHerCard(modifier = modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = SafeHerTextSecondary,
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
fun AiEmergencyConfirmationCard(
    promptKind: String,
    secondsRemaining: Int,
    onConfirmSafe: () -> Unit,
    onConfirmSos: () -> Unit,
    modifier: Modifier = Modifier,
    title: String? = null,
    body: String? = null,
    confirmLabel: String? = null,
    dismissLabel: String? = null,
    showCountdown: Boolean = true,
) {
    val isEmergency = promptKind.equals("EMERGENCY", ignoreCase = true)
    val resolvedTitle = title ?: stringResource(
        if (isEmergency) R.string.ai_confirm_emergency_title
        else R.string.ai_confirm_suspicious_title,
    )
    val resolvedBody = body ?: stringResource(
        if (isEmergency) R.string.ai_confirm_emergency_body
        else R.string.ai_confirm_suspicious_body,
    )
    val resolvedConfirm = confirmLabel ?: stringResource(R.string.ai_emergency_confirm_yes)
    val resolvedDismiss = dismissLabel ?: stringResource(R.string.ai_emergency_confirm_no)
    SafeHerCard(modifier = modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                text = resolvedTitle,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = resolvedBody,
                style = MaterialTheme.typography.bodyMedium,
                color = SafeHerTextSecondary,
            )
            if (showCountdown) {
                Text(
                    text = stringResource(R.string.ai_confirm_countdown, secondsRemaining),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Text(
                text = stringResource(R.string.ai_confirm_no_auto_sos),
                style = MaterialTheme.typography.bodySmall,
                color = SafeHerTextSecondary,
            )
            androidx.compose.foundation.layout.Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                androidx.compose.material3.OutlinedButton(
                    onClick = onConfirmSafe,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(resolvedDismiss)
                }
                androidx.compose.material3.Button(
                    onClick = onConfirmSos,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(resolvedConfirm)
                }
            }
        }
    }
}
