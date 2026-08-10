package com.safeher.app.feature.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerIcons
import com.safeher.app.core.designsystem.SafeHerLightPink
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.core.designsystem.components.SafeHerCard
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.ProfileLoadingView
import com.safeher.app.feature.home.components.SafeHerScreenHeader
import kotlinx.coroutines.flow.collectLatest

@Composable
fun ProfileScreen(
    onNavigateToLogin: () -> Unit,
    onNavigateToSettings: () -> Unit = {},
    onNavigateToContacts: () -> Unit = {},
    onNavigateToAbout: () -> Unit = {},
    onNavigateToSecurity: () -> Unit = {},
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                ProfileEvent.NavigateToLogin -> onNavigateToLogin()
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
            uiState.isLoading -> ProfileLoadingView()
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
            uiState.profile != null -> ProfileContent(
                uiState = uiState,
                onLogout = viewModel::logout,
                onNavigateToSettings = onNavigateToSettings,
                onNavigateToContacts = onNavigateToContacts,
                onNavigateToAbout = onNavigateToAbout,
                onNavigateToSecurity = onNavigateToSecurity,
            )
        }
    }
}

@Composable
private fun ProfileContent(
    uiState: ProfileUiState,
    onLogout: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToContacts: () -> Unit,
    onNavigateToAbout: () -> Unit,
    onNavigateToSecurity: () -> Unit,
) {
    val profile = uiState.profile ?: return

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        SafeHerScreenHeader(title = stringResource(R.string.nav_profile))

        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SafeHerCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(88.dp)
                            .clip(CircleShape)
                            .background(SafeHerLightPink),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = profile.name.firstOrNull()?.uppercase() ?: "?",
                            style = MaterialTheme.typography.headlineMedium,
                            color = SafeHerPrimary,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = profile.name,
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Icon(
                            imageVector = SafeHerIcons.Edit,
                            contentDescription = null,
                            tint = SafeHerTextSecondary,
                            modifier = Modifier
                                .padding(start = 6.dp)
                                .size(18.dp),
                        )
                    }
                    Text(
                        text = profile.phoneNumber,
                        style = MaterialTheme.typography.bodyMedium,
                        color = SafeHerTextSecondary,
                    )
                    Text(
                        text = profile.city?.takeIf { it.isNotBlank() }
                            ?: stringResource(R.string.profile_city_not_set),
                        style = MaterialTheme.typography.bodySmall,
                        color = SafeHerTextSecondary,
                    )
                }
            }

            ProfileMenuItem(
                title = stringResource(R.string.profile_personal_info),
                icon = SafeHerIcons.Profile,
                onClick = onNavigateToSettings,
            )
            ProfileMenuItem(
                title = stringResource(R.string.profile_emergency_info),
                icon = SafeHerIcons.EmergencyContacts,
                onClick = onNavigateToContacts,
            )
            ProfileMenuItem(
                title = stringResource(R.string.profile_help_support),
                icon = SafeHerIcons.Help,
                onClick = onNavigateToSettings,
            )
            ProfileMenuItem(
                title = stringResource(R.string.profile_privacy_security),
                icon = SafeHerIcons.Security,
                onClick = onNavigateToSecurity,
            )
            ProfileMenuItem(
                title = stringResource(R.string.profile_about),
                icon = SafeHerIcons.Shield,
                onClick = onNavigateToAbout,
            )

            Spacer(modifier = Modifier.height(8.dp))

            Button(
                onClick = onLogout,
                enabled = !uiState.isLoggingOut,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                ),
            ) {
                if (uiState.isLoggingOut) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onError,
                    )
                } else {
                    Text(stringResource(R.string.logout))
                }
            }
        }
    }
}

@Composable
private fun ProfileMenuItem(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit,
) {
    SafeHerCard(modifier = Modifier.fillMaxWidth(), onClick = onClick) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
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
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = SafeHerIcons.Forward,
                contentDescription = null,
                tint = SafeHerTextSecondary,
            )
        }
    }
}
