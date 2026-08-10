package com.safeher.app.feature.home.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.SafeHerIcons

@Composable
fun HomeHeader(
    userName: String,
    isProtected: Boolean,
    modifier: Modifier = Modifier,
    onMenuClick: () -> Unit = {},
    onNotificationClick: () -> Unit = {},
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onMenuClick, modifier = Modifier.size(48.dp)) {
            Icon(
                imageVector = SafeHerIcons.Menu,
                contentDescription = stringResource(R.string.home_menu),
                tint = SafeHerTextSecondary,
            )
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.weight(1f),
        ) {
            Text(
                text = stringResource(R.string.home_greeting, userName),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                text = if (isProtected) {
                    stringResource(R.string.home_protected)
                } else {
                    stringResource(R.string.home_not_protected)
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (isProtected) SafeHerPrimary else SafeHerTextSecondary,
            )
        }

        IconButton(onClick = onNotificationClick, modifier = Modifier.size(48.dp)) {
            Icon(
                imageVector = SafeHerIcons.NotificationOutlined,
                contentDescription = stringResource(R.string.home_notifications),
                tint = SafeHerTextSecondary,
            )
        }
    }
}

@Composable
fun SafeHerScreenHeader(
    title: String,
    modifier: Modifier = Modifier,
    showBack: Boolean = false,
    onBack: () -> Unit = {},
    actionIcon: androidx.compose.ui.graphics.vector.ImageVector? = null,
    onActionClick: () -> Unit = {},
    actionContentDescription: String? = null,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (showBack) {
            IconButton(onClick = onBack, modifier = Modifier.size(48.dp)) {
                Icon(
                    imageVector = SafeHerIcons.Back,
                    contentDescription = stringResource(R.string.action_back),
                    tint = SafeHerTextSecondary,
                )
            }
        } else {
            Box(modifier = Modifier.size(48.dp))
        }

        Text(
            text = title,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.weight(1f),
            color = MaterialTheme.colorScheme.onBackground,
        )

        if (actionIcon != null) {
            IconButton(onClick = onActionClick, modifier = Modifier.size(48.dp)) {
                Icon(
                    imageVector = actionIcon,
                    contentDescription = actionContentDescription,
                    tint = SafeHerTextSecondary,
                )
            }
        } else {
            Box(modifier = Modifier.size(48.dp))
        }
    }
}
