package com.safeher.app.feature.home.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.core.designsystem.SafeHerNavInactive
import com.safeher.app.core.designsystem.SafeHerOnPrimary
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.ui.navigation.Route
import com.safeher.app.feature.dashboard.DashboardRoutes

@Composable
fun HomeBottomNavigation(
    currentRoute: String?,
    onNavigate: (String) -> Unit,
) {
    val items = listOf(
        BottomNavItem(DashboardRoutes.DASHBOARD, stringResource(R.string.nav_home), SafeHerIcons.Home),
        BottomNavItem(Route.SOS, stringResource(R.string.nav_alerts), SafeHerIcons.NotificationOutlined),
        BottomNavItem(Route.AI, stringResource(R.string.nav_ai_monitor), SafeHerIcons.Microphone, isCenter = true),
        BottomNavItem(Route.SOS_HISTORY, stringResource(R.string.nav_history), SafeHerIcons.History),
        BottomNavItem(DashboardRoutes.PROFILE, stringResource(R.string.nav_profile), SafeHerIcons.Profile),
    )

    NavigationBar(
        containerColor = MaterialTheme.colorScheme.surface,
        contentColor = SafeHerNavInactive,
        tonalElevation = 0.dp,
        modifier = Modifier.fillMaxWidth(),
    ) {
        items.forEach { item ->
            if (item.isCenter) {
                NavigationBarItem(
                    selected = currentRoute?.startsWith("ai") == true,
                    onClick = { onNavigate(item.route) },
                    icon = {
                        Box(
                            modifier = Modifier
                                .offset(y = (-12).dp)
                                .size(56.dp)
                                .clip(CircleShape)
                                .background(SafeHerPrimary)
                                .clickable { onNavigate(item.route) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(
                                imageVector = item.icon,
                                contentDescription = item.label,
                                tint = SafeHerOnPrimary,
                                modifier = Modifier.size(26.dp),
                            )
                        }
                    },
                    label = {
                        Text(
                            text = item.label,
                            style = MaterialTheme.typography.labelSmall,
                        )
                    },
                    colors = centerNavColors(),
                )
            } else {
                val selected = when (item.route) {
                    DashboardRoutes.DASHBOARD -> currentRoute == DashboardRoutes.DASHBOARD
                    DashboardRoutes.PROFILE -> currentRoute == DashboardRoutes.PROFILE
                    Route.SOS -> currentRoute?.startsWith("sos") == true &&
                        currentRoute != Route.SOS_HISTORY
                    Route.SOS_HISTORY -> currentRoute == Route.SOS_HISTORY
                    else -> currentRoute == item.route
                }
                NavigationBarItem(
                    selected = selected,
                    onClick = { onNavigate(item.route) },
                    icon = {
                        Icon(
                            imageVector = item.icon,
                            contentDescription = item.label,
                            modifier = Modifier.size(24.dp),
                        )
                    },
                    label = {
                        Text(
                            text = item.label,
                            style = MaterialTheme.typography.labelSmall,
                        )
                    },
                    colors = standardNavColors(),
                )
            }
        }
    }
}

@Composable
private fun standardNavColors() = NavigationBarItemDefaults.colors(
    selectedIconColor = SafeHerPrimary,
    selectedTextColor = SafeHerPrimary,
    unselectedIconColor = SafeHerNavInactive,
    unselectedTextColor = SafeHerNavInactive,
    indicatorColor = MaterialTheme.colorScheme.surface,
)

@Composable
private fun centerNavColors() = NavigationBarItemDefaults.colors(
    selectedIconColor = SafeHerPrimary,
    selectedTextColor = SafeHerPrimary,
    unselectedIconColor = SafeHerNavInactive,
    unselectedTextColor = SafeHerNavInactive,
    indicatorColor = MaterialTheme.colorScheme.surface,
)

private data class BottomNavItem(
    val route: String,
    val label: String,
    val icon: ImageVector,
    val isCenter: Boolean = false,
)
