package com.safeher.app.feature.location.components

import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.safeher.app.R

@Composable
fun TrackingStatusChip(
    isTracking: Boolean,
    modifier: Modifier = Modifier,
) {
    val (label, containerColor, labelColor) = if (isTracking) {
        Triple(
            stringResource(R.string.location_tracking_active),
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
    } else {
        Triple(
            stringResource(R.string.location_tracking_inactive),
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
