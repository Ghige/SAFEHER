package com.safeher.app.feature.ai.components

import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.safeher.app.R
import com.safeher.app.domain.model.AiAction

@Composable
fun DetectionStatusChip(
    action: AiAction,
    modifier: Modifier = Modifier,
) {
    val (label, color) = when (action) {
        AiAction.NOTHING -> stringResource(R.string.ai_action_nothing) to MaterialTheme.colorScheme.outline
        AiAction.SILENT_VIBRATION -> stringResource(R.string.ai_action_silent) to MaterialTheme.colorScheme.tertiary
        AiAction.CONFIRM_30S -> stringResource(R.string.ai_action_confirm) to MaterialTheme.colorScheme.secondary
        AiAction.FIRE_IMMEDIATELY -> stringResource(R.string.ai_action_fire) to MaterialTheme.colorScheme.error
    }
    AssistChip(
        onClick = {},
        label = { Text(label) },
        modifier = modifier,
        enabled = false,
        colors = AssistChipDefaults.assistChipColors(
            disabledContainerColor = color.copy(alpha = 0.15f),
            disabledLabelColor = color,
        ),
    )
}
