package com.safeher.app.feature.sos.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.components.SafeHerCard
import com.safeher.app.domain.model.SafetyAlert

@Composable
fun AlertHistoryCard(
    alert: SafetyAlert,
    modifier: Modifier = Modifier,
) {
    SafeHerCard(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = historyTitle(alert),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = historySubtitle(alert),
                    style = MaterialTheme.typography.bodySmall,
                    color = SafeHerTextSecondary,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = alert.startedAt,
                    style = MaterialTheme.typography.bodySmall,
                    color = SafeHerTextSecondary,
                )
            }
            EmergencyStatusChip(status = alert.status)
        }
    }
}

@Composable
private fun historyTitle(alert: SafetyAlert): String {
    return when {
        alert.triggerType.contains("ai", ignoreCase = true) ||
            alert.triggerType.contains("audio", ignoreCase = true) ->
            stringResource(R.string.history_item_ai_title)
        alert.triggerType.contains("location", ignoreCase = true) ->
            stringResource(R.string.history_item_location_title)
        else -> stringResource(R.string.history_item_sos_title)
    }
}

@Composable
private fun historySubtitle(alert: SafetyAlert): String {
    return when {
        alert.triggerType.contains("ai", ignoreCase = true) ||
            alert.triggerType.contains("audio", ignoreCase = true) ->
            stringResource(R.string.history_item_ai_subtitle)
        alert.triggerType.contains("location", ignoreCase = true) ->
            stringResource(R.string.history_item_location_subtitle)
        else -> stringResource(R.string.history_item_sos_subtitle)
    }
}
