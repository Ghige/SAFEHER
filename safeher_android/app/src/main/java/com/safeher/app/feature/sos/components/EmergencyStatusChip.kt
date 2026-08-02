package com.safeher.app.feature.sos.components

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safeher.app.R

@Composable
fun EmergencyStatusChip(
    status: String,
    modifier: Modifier = Modifier,
) {
    val (label, containerColor, labelColor) = when (status.lowercase()) {
        "active" -> Triple(
            stringResource(R.string.sos_status_active),
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
        "escalated" -> Triple(
            stringResource(R.string.sos_status_escalated),
            MaterialTheme.colorScheme.error,
            MaterialTheme.colorScheme.onError,
        )
        "cancelled" -> Triple(
            stringResource(R.string.sos_status_cancelled),
            MaterialTheme.colorScheme.surfaceVariant,
            MaterialTheme.colorScheme.onSurfaceVariant,
        )
        "resolved" -> Triple(
            stringResource(R.string.sos_status_resolved),
            MaterialTheme.colorScheme.primaryContainer,
            MaterialTheme.colorScheme.onPrimaryContainer,
        )
        else -> Triple(
            status.replaceFirstChar { it.uppercase() },
            MaterialTheme.colorScheme.surfaceVariant,
            MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    AssistChip(
        onClick = {},
        enabled = false,
        modifier = modifier,
        label = { Text(label) },
        colors = AssistChipDefaults.assistChipColors(
            containerColor = containerColor,
            labelColor = labelColor,
            disabledContainerColor = containerColor,
            disabledLabelColor = labelColor,
        ),
        border = null,
    )
}
