package com.safeher.app.feature.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContactEmergency
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.LoadingView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.ProfileCard
import com.safeher.app.feature.home.components.QuickActionCard
import com.safeher.app.feature.home.components.StatusCard
import kotlinx.coroutines.flow.collectLatest

private data class QuickActionItem(
    val feature: QuickActionFeature,
    val icon: ImageVector,
)

@Composable
fun DashboardScreen(
    onNavigateToComingSoon: (String) -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: DashboardViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                is DashboardEvent.NavigateToComingSoon -> onNavigateToComingSoon(event.feature)
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding),
    ) {
        if (uiState.isOffline) {
            Surface(color = MaterialTheme.colorScheme.errorContainer) {
                OfflineBanner()
            }
        }

        when {
            uiState.isLoading -> LoadingView()
            uiState.error != null -> {
                ErrorView(
                    message = uiState.error.orEmpty(),
                    onRetry = viewModel::loadProfile,
                    errorType = when {
                        uiState.isOffline -> ErrorType.OFFLINE
                        uiState.isEmpty -> ErrorType.EMPTY
                        uiState.error.orEmpty().contains("offline", ignoreCase = true) -> ErrorType.OFFLINE
                        else -> ErrorType.NETWORK
                    },
                )
            }
            uiState.profile != null -> DashboardContent(
                uiState = uiState,
                onQuickAction = viewModel::onQuickAction,
            )
        }
    }
}

@Composable
private fun DashboardContent(
    uiState: DashboardUiState,
    onQuickAction: (QuickActionFeature) -> Unit,
) {
    val profile = uiState.profile ?: return

    val quickActions = listOf(
        QuickActionItem(QuickActionFeature.CONTACTS, Icons.Default.ContactEmergency),
        QuickActionItem(QuickActionFeature.SOS, Icons.Default.Shield),
        QuickActionItem(QuickActionFeature.AI, Icons.Default.Psychology),
        QuickActionItem(QuickActionFeature.HELPERS, Icons.Default.People),
        QuickActionItem(QuickActionFeature.LIVE_LOCATION, Icons.Default.LocationOn),
        QuickActionItem(QuickActionFeature.SETTINGS, Icons.Default.Settings),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            text = stringResource(R.string.dashboard_welcome, profile.name),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = stringResource(R.string.dashboard_subtitle),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(modifier = Modifier.height(20.dp))

        ProfileCard(profile = profile)
        Spacer(modifier = Modifier.height(16.dp))

        StatusCard(
            title = if (profile.isVerified) {
                stringResource(R.string.status_verified)
            } else {
                stringResource(R.string.status_unverified)
            },
            subtitle = if (profile.isVerified) {
                stringResource(R.string.dashboard_verified_subtitle)
            } else {
                stringResource(R.string.dashboard_unverified_subtitle)
            },
            icon = Icons.Default.Shield,
        )
        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = stringResource(R.string.dashboard_quick_actions),
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(12.dp))

        quickActions.chunked(2).forEach { rowItems ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                rowItems.forEach { item ->
                    QuickActionCard(
                        title = stringResource(item.feature.titleRes),
                        icon = item.icon,
                        onClick = { onQuickAction(item.feature) },
                        modifier = Modifier.weight(1f),
                    )
                }
                if (rowItems.size == 1) {
                    Spacer(modifier = Modifier.weight(1f))
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
        }
    }
}
