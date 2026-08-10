package com.safeher.app.feature.home.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.core.designsystem.SafeHerLightPink
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.components.SafeHerCard
import com.safeher.app.core.designsystem.components.SafeHerStatusBadge

@Composable
fun FeatureNavCard(
    title: String,
    subtitle: String,
    statusLabel: String,
    isActive: Boolean,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    trailingContent: @Composable (() -> Unit)? = null,
) {
    SafeHerCard(modifier = modifier.fillMaxWidth(), onClick = onClick) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(SafeHerLightPink),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = SafeHerPrimary,
                    modifier = Modifier.size(22.dp),
                )
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = SafeHerTextSecondary,
                )
                SafeHerStatusBadge(
                    text = statusLabel,
                    isActive = isActive,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }

            trailingContent?.invoke() ?: Icon(
                imageVector = SafeHerIcons.Forward,
                contentDescription = null,
                tint = SafeHerTextSecondary,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

@Composable
fun ContactAvatarRow(
    names: List<String>,
    modifier: Modifier = Modifier,
) {
    Row(modifier = modifier, horizontalArrangement = Arrangement.spacedBy((-8).dp)) {
        names.take(3).forEach { name ->
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(SafeHerLightPink),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = name.firstOrNull()?.uppercase() ?: "?",
                    style = MaterialTheme.typography.labelMedium,
                    color = SafeHerPrimary,
                )
            }
        }
    }
}

@Composable
fun SafeHerQuickActionTile(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    SafeHerCard(modifier = modifier, onClick = onClick) {
        Column(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            horizontalAlignment = Alignment.Start,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(SafeHerLightPink),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = SafeHerPrimary,
                    modifier = Modifier.size(20.dp),
                )
            }
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = SafeHerTextSecondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
fun SafetyReassuranceCard(
    modifier: Modifier = Modifier,
) {
    SafeHerCard(modifier = modifier.fillMaxWidth()) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = SafeHerIcons.Shield,
                contentDescription = null,
                tint = SafeHerPrimary,
                modifier = Modifier.size(48.dp),
            )
            Column {
                Text(
                    text = "You are safe. We are with you.",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "Stay alert, stay safe.",
                    style = MaterialTheme.typography.bodySmall,
                    color = SafeHerTextSecondary,
                )
            }
        }
    }
}
