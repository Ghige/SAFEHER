package com.safeher.app.feature.settings.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.domain.model.PermissionDisplayStatus

@Composable
fun PermissionStatusCard(
    title: String,
    status: PermissionDisplayStatus,
    onRequest: (() -> Unit)? = null,
    onOpenSettings: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val statusLabel = when (status) {
        PermissionDisplayStatus.GRANTED -> stringResource(R.string.settings_permission_granted)
        PermissionDisplayStatus.DENIED -> stringResource(R.string.settings_permission_denied)
        PermissionDisplayStatus.PERMANENTLY_DENIED -> stringResource(R.string.settings_permission_permanently_denied)
        PermissionDisplayStatus.NOT_REQUESTED -> stringResource(R.string.settings_permission_not_requested)
    }
    val statusColor = when (status) {
        PermissionDisplayStatus.GRANTED -> MaterialTheme.colorScheme.primary
        PermissionDisplayStatus.PERMANENTLY_DENIED -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    SettingsCard(modifier = modifier) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                Text(text = statusLabel, color = statusColor, style = MaterialTheme.typography.labelLarge)
            }
            when (status) {
                PermissionDisplayStatus.DENIED -> {
                    if (onRequest != null) {
                        Button(onClick = onRequest, modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(R.string.settings_grant_permission))
                        }
                    }
                }
                PermissionDisplayStatus.PERMANENTLY_DENIED, PermissionDisplayStatus.NOT_REQUESTED -> {
                    if (onOpenSettings != null) {
                        Button(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(R.string.settings_open_system_settings))
                        }
                    }
                }
                PermissionDisplayStatus.GRANTED -> Unit
            }
        }
    }
}
