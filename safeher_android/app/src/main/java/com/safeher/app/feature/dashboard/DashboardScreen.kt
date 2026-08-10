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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.core.designsystem.components.PinkWaveform
import com.safeher.app.feature.home.components.ContactAvatarRow
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.FeatureNavCard
import com.safeher.app.feature.home.components.HomeHeader
import com.safeher.app.feature.home.components.LoadingView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.SafeHerQuickActionTile
import com.safeher.app.feature.home.components.SafetyReassuranceCard
import com.safeher.app.feature.sos.components.HomeSosSection
import kotlinx.coroutines.flow.collectLatest

@Composable
fun DashboardScreen(
    onNavigateToComingSoon: (String) -> Unit,
    onSosClick: () -> Unit,
    onNavigateToSettings: () -> Unit = {},
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
                onSosClick = onSosClick,
                onNavigate = { feature -> viewModel.onNavigate(feature) },
                onMenuClick = onNavigateToSettings,
            )
            else -> LoadingView()
        }
    }
}

@Composable
private fun DashboardContent(
    uiState: DashboardUiState,
    onSosClick: () -> Unit,
    onNavigate: (QuickActionFeature) -> Unit,
    onMenuClick: () -> Unit,
) {
    val profile = uiState.profile ?: return
    val contactCount = uiState.emergencyContacts.size
    val contactNames = uiState.emergencyContacts.map { it.name }

    val aiStatusLabel = when (uiState.aiStatus) {
        AiHomeStatus.NORMAL -> stringResource(R.string.ai_status_normal)
        AiHomeStatus.LISTENING -> stringResource(R.string.ai_status_listening)
        AiHomeStatus.DETECTING -> stringResource(R.string.ai_status_detecting)
        AiHomeStatus.OFF -> stringResource(R.string.ai_status_off)
    }

    val locationStatusLabel = if (uiState.isLocationSharingActive) {
        stringResource(R.string.status_active)
    } else {
        stringResource(R.string.status_inactive)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        HomeHeader(
            userName = profile.name,
            isProtected = profile.isVerified,
            onMenuClick = onMenuClick,
            onNotificationClick = onMenuClick,
        )

        HomeSosSection(
            onSosClick = onSosClick,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
        )

        Column(
            modifier = Modifier.padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            FeatureNavCard(
                title = stringResource(R.string.home_live_location_title),
                subtitle = stringResource(R.string.home_sharing_with_contacts, contactCount.coerceAtLeast(0)),
                statusLabel = locationStatusLabel,
                isActive = uiState.isLocationSharingActive,
                icon = SafeHerIcons.Location,
                onClick = { onNavigate(QuickActionFeature.LIVE_LOCATION) },
            )

            FeatureNavCard(
                title = stringResource(R.string.home_ai_voice_title),
                subtitle = stringResource(R.string.home_ai_voice_subtitle),
                statusLabel = aiStatusLabel,
                isActive = uiState.aiStatus == AiHomeStatus.LISTENING ||
                    uiState.aiStatus == AiHomeStatus.DETECTING,
                icon = SafeHerIcons.Microphone,
                onClick = { onNavigate(QuickActionFeature.AI) },
                trailingContent = {
                    PinkWaveform(
                        isActive = uiState.aiIsMonitoring,
                        modifier = Modifier
                            .fillMaxWidth(0.35f)
                            .height(32.dp),
                        barCount = 12,
                    )
                },
            )

            FeatureNavCard(
                title = stringResource(R.string.action_contacts),
                subtitle = stringResource(R.string.home_contacts_saved, contactCount),
                statusLabel = stringResource(R.string.home_contacts_status),
                isActive = contactCount > 0,
                icon = SafeHerIcons.EmergencyContacts,
                onClick = { onNavigate(QuickActionFeature.CONTACTS) },
                trailingContent = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        if (contactNames.isNotEmpty()) {
                            ContactAvatarRow(names = contactNames)
                        }
                        androidx.compose.material3.Icon(
                            imageVector = SafeHerIcons.Forward,
                            contentDescription = null,
                            tint = com.safeher.app.core.designsystem.SafeHerTextSecondary,
                            modifier = Modifier.padding(start = 4.dp),
                        )
                    }
                },
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                SafeHerQuickActionTile(
                    title = stringResource(R.string.home_quick_ai),
                    subtitle = aiStatusLabel,
                    icon = SafeHerIcons.Microphone,
                    onClick = { onNavigate(QuickActionFeature.AI) },
                    modifier = Modifier.weight(1f),
                )
                SafeHerQuickActionTile(
                    title = stringResource(R.string.home_quick_contacts),
                    subtitle = stringResource(R.string.home_contacts_saved, contactCount),
                    icon = SafeHerIcons.EmergencyContacts,
                    onClick = { onNavigate(QuickActionFeature.CONTACTS) },
                    modifier = Modifier.weight(1f),
                )
                SafeHerQuickActionTile(
                    title = stringResource(R.string.home_quick_history),
                    subtitle = stringResource(R.string.home_quick_history_sub),
                    icon = SafeHerIcons.History,
                    onClick = { onNavigate(QuickActionFeature.HISTORY) },
                    modifier = Modifier.weight(1f),
                )
            }

            SafetyReassuranceCard()
            Spacer(modifier = Modifier.height(8.dp))
        }
    }
}
