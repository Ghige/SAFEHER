package com.safeher.app.feature.location.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.services.LocationPermissionStatus

@Composable
fun PermissionCard(
    permissionStatus: LocationPermissionStatus,
    isGpsEnabled: Boolean,
    onRequestPermission: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onOpenLocationSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.35f),
        ),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                text = when {
                    !isGpsEnabled -> stringResource(R.string.location_gps_disabled_title)
                    permissionStatus == LocationPermissionStatus.PERMANENTLY_DENIED ->
                        stringResource(R.string.location_permission_denied_title)
                    else -> stringResource(R.string.location_permission_required_title)
                },
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = when {
                    !isGpsEnabled -> stringResource(R.string.location_gps_disabled_message)
                    permissionStatus == LocationPermissionStatus.PERMANENTLY_DENIED ->
                        stringResource(R.string.location_permission_denied_message)
                    else -> stringResource(R.string.location_permission_required_message)
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(modifier = Modifier.height(16.dp))
            when {
                !isGpsEnabled -> {
                    Button(onClick = onOpenLocationSettings, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.location_open_settings))
                    }
                }
                permissionStatus == LocationPermissionStatus.PERMANENTLY_DENIED -> {
                    Button(onClick = onOpenAppSettings, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.location_open_app_settings))
                    }
                }
                else -> {
                    Button(onClick = onRequestPermission, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.location_grant_permission))
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedButton(onClick = onOpenLocationSettings, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.location_open_settings))
                    }
                }
            }
        }
    }
}
