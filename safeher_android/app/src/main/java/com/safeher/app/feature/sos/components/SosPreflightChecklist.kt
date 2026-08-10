package com.safeher.app.feature.sos.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BatteryAlert
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.feature.sos.util.SosPreflightCheck
import com.safeher.app.feature.sos.util.SosPreflightItem
import com.safeher.app.feature.sos.util.SosPreflightResult
import com.safeher.app.feature.sos.util.SosPreflightStatus

@Composable
fun SosPreflightChecklist(
    preflight: SosPreflightResult,
    onOpenLocationSettings: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onOpenBatterySettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val cardAlpha by animateFloatAsState(
        targetValue = if (preflight.allRecommendedMet) 0.92f else 1f,
        animationSpec = tween(400),
        label = "preflight_alpha",
    )

    Card(
        modifier = modifier
            .fillMaxWidth()
            .alpha(cardAlpha),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (preflight.allRecommendedMet) {
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
            } else {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f)
            },
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = stringResource(R.string.sos_preflight_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = if (preflight.allRecommendedMet) {
                    stringResource(R.string.sos_preflight_all_clear)
                } else {
                    stringResource(R.string.sos_preflight_warnings, preflight.warningCount)
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(8.dp))
            preflight.items.forEach { item ->
                PreflightRow(
                    item = item,
                    onFix = when (item.check) {
                        SosPreflightCheck.LOCATION_PERMISSION,
                        SosPreflightCheck.BACKGROUND_LOCATION,
                        -> onOpenAppSettings
                        SosPreflightCheck.GPS_ENABLED -> onOpenLocationSettings
                        SosPreflightCheck.BATTERY_OPTIMIZATION -> onOpenBatterySettings
                    },
                )
            }
        }
    }
}

@Composable
private fun PreflightRow(
    item: SosPreflightItem,
    onFix: () -> Unit,
) {
    val isOk = item.status == SosPreflightStatus.OK
    val tint by animateColorAsState(
        targetValue = if (isOk) {
            MaterialTheme.colorScheme.primary
        } else {
            MaterialTheme.colorScheme.error
        },
        animationSpec = tween(300),
        label = "preflight_tint",
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(
            imageVector = if (isOk) Icons.Default.CheckCircle else iconForCheck(item.check),
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(22.dp),
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = titleForCheck(item.check),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = if (isOk) FontWeight.Normal else FontWeight.Medium,
            )
            if (!isOk) {
                Text(
                    text = subtitleForCheck(item.check),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (!isOk) {
            TextButton(onClick = onFix) {
                Text(stringResource(R.string.sos_preflight_fix))
            }
        }
    }
}

@Composable
private fun titleForCheck(check: SosPreflightCheck): String = when (check) {
    SosPreflightCheck.LOCATION_PERMISSION -> stringResource(R.string.sos_preflight_location)
    SosPreflightCheck.GPS_ENABLED -> stringResource(R.string.sos_preflight_gps)
    SosPreflightCheck.BACKGROUND_LOCATION -> stringResource(R.string.sos_preflight_background)
    SosPreflightCheck.BATTERY_OPTIMIZATION -> stringResource(R.string.sos_preflight_battery)
}

@Composable
private fun subtitleForCheck(check: SosPreflightCheck): String = when (check) {
    SosPreflightCheck.LOCATION_PERMISSION -> stringResource(R.string.sos_preflight_location_hint)
    SosPreflightCheck.GPS_ENABLED -> stringResource(R.string.sos_preflight_gps_hint)
    SosPreflightCheck.BACKGROUND_LOCATION -> stringResource(R.string.sos_preflight_background_hint)
    SosPreflightCheck.BATTERY_OPTIMIZATION -> stringResource(R.string.sos_preflight_battery_hint)
}

private fun iconForCheck(check: SosPreflightCheck): ImageVector = when (check) {
    SosPreflightCheck.LOCATION_PERMISSION -> Icons.Default.LocationOn
    SosPreflightCheck.GPS_ENABLED -> Icons.Default.MyLocation
    SosPreflightCheck.BACKGROUND_LOCATION -> Icons.Default.LocationOn
    SosPreflightCheck.BATTERY_OPTIMIZATION -> Icons.Default.BatteryAlert
}

@Composable
fun SosLocationWarningBanner(
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(
                color = MaterialTheme.colorScheme.errorContainer,
                shape = RoundedCornerShape(12.dp),
            )
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onErrorContainer,
        )
        Text(
            text = stringResource(R.string.sos_location_unavailable_warning),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

@Composable
fun SosAlertWarningBanner(
    message: String,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(
                color = MaterialTheme.colorScheme.tertiaryContainer,
                shape = RoundedCornerShape(12.dp),
            )
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onTertiaryContainer,
        )
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onTertiaryContainer,
        )
    }
}
