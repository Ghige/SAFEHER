package com.safeher.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.BatteryAlert
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PrivacyTip
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.services.ai.AiFeatureFlags
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.VerificationBadge
import com.safeher.app.feature.settings.components.LoadingSettings
import com.safeher.app.feature.settings.components.SectionHeader
import com.safeher.app.feature.settings.components.SettingsCard
import com.safeher.app.feature.settings.components.SettingsItem
import com.safeher.app.feature.settings.components.TogglePreference
import kotlinx.coroutines.flow.collectLatest

@Composable
fun SettingsScreen(
    onNavigate: (SettingsEvent) -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                SettingsEvent.NavigateToLogin -> onNavigate(event)
                else -> onNavigate(event)
            }
        }
    }

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            when {
                uiState.isLoading -> LoadingSettings()
                else -> SettingsContent(uiState = uiState, viewModel = viewModel)
            }
        }
    }
}

@Composable
private fun SettingsContent(
    uiState: SettingsUiState,
    viewModel: SettingsViewModel,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionHeader(stringResource(R.string.settings_section_account))
        SettingsCard {
            uiState.profile?.let { profile ->
                SettingsItem(
                    title = profile.name,
                    subtitle = profile.phoneNumber,
                    icon = Icons.Default.Person,
                    onClick = { viewModel.navigateTo(SettingsEvent.NavigateToProfile) },
                )
                Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    VerificationBadge(isVerified = profile.isVerified, onContainer = true)
                }
            }
            SettingsItem(
                title = stringResource(R.string.settings_security),
                icon = Icons.Default.Security,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToSecurity) },
            )
            Button(
                onClick = viewModel::logout,
                enabled = !uiState.isLoggingOut,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
            ) {
                if (uiState.isLoggingOut) {
                    CircularProgressIndicator(strokeWidth = 2.dp)
                } else {
                    Text(stringResource(R.string.logout))
                }
            }
        }

        SectionHeader(stringResource(R.string.settings_section_ai))
        SettingsCard {
            SettingsItem(
                title = stringResource(R.string.ai_monitoring_toggle),
                subtitle = if (uiState.aiMonitoringEnabled) {
                    stringResource(R.string.settings_ai_monitoring_on)
                } else {
                    stringResource(R.string.settings_ai_monitoring_off)
                },
                icon = Icons.Default.SmartToy,
            )
            TogglePreference(
                title = stringResource(R.string.settings_ai_audio),
                checked = uiState.aiAudioDetectionEnabled,
                onCheckedChange = viewModel::setAiAudioDetectionEnabled,
            )
            if (AiFeatureFlags.MOVEMENT_AI_ENABLED) {
                TogglePreference(
                    title = stringResource(R.string.settings_ai_movement),
                    checked = uiState.aiMovementDetectionEnabled,
                    onCheckedChange = viewModel::setAiMovementDetectionEnabled,
                )
            } else {
                SettingsItem(
                    title = stringResource(R.string.settings_ai_movement),
                    subtitle = stringResource(R.string.settings_ai_movement_coming_soon),
                )
            }
            TogglePreference(
                title = stringResource(R.string.settings_ai_help_improve),
                subtitle = stringResource(R.string.settings_ai_help_improve_desc),
                checked = uiState.aiHelpImproveEnabled,
                onCheckedChange = viewModel::setAiHelpImproveEnabled,
            )
            SettingsItem(
                title = stringResource(R.string.settings_ai_sensitivity),
                trailing = uiState.aiSensitivity.label,
                icon = Icons.Default.SmartToy,
                onClick = {
                    val next = when (uiState.aiSensitivity) {
                        AiSensitivity.LOW -> AiSensitivity.MEDIUM
                        AiSensitivity.MEDIUM -> AiSensitivity.HIGH
                        AiSensitivity.HIGH -> AiSensitivity.LOW
                    }
                    viewModel.setAiSensitivity(next)
                },
            )
        }

        SectionHeader(stringResource(R.string.settings_section_notifications))
        SettingsCard {
            TogglePreference(
                title = stringResource(R.string.settings_notifications_enable),
                checked = uiState.notificationsEnabled,
                onCheckedChange = viewModel::setNotificationsEnabled,
            )
            SettingsItem(
                title = stringResource(R.string.settings_notifications_manage),
                icon = Icons.Default.Notifications,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToNotifications) },
            )
        }

        SectionHeader(stringResource(R.string.settings_section_permissions))
        SettingsCard {
            SettingsItem(
                title = stringResource(R.string.settings_permissions),
                icon = Icons.Default.VerifiedUser,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToPermissions) },
            )
            SettingsItem(
                title = stringResource(R.string.settings_battery),
                subtitle = if (uiState.isBatteryOptimizationDisabled) {
                    stringResource(R.string.settings_battery_ok)
                } else {
                    stringResource(R.string.settings_battery_restricted)
                },
                icon = Icons.Default.BatteryAlert,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToBattery) },
            )
        }

        SectionHeader(stringResource(R.string.settings_section_appearance))
        SettingsCard {
            SettingsItem(
                title = stringResource(R.string.settings_theme),
                trailing = uiState.themeMode.storageKey.replaceFirstChar { it.uppercase() },
                onClick = {
                    val next = when (uiState.themeMode) {
                        AppThemeMode.SYSTEM -> AppThemeMode.LIGHT
                        AppThemeMode.LIGHT -> AppThemeMode.DARK
                        AppThemeMode.DARK -> AppThemeMode.SYSTEM
                    }
                    viewModel.setThemeMode(next)
                },
            )
        }

        SectionHeader(stringResource(R.string.settings_section_about))
        SettingsCard {
            SettingsItem(
                title = stringResource(R.string.settings_about),
                icon = Icons.Default.Info,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToAbout) },
            )
            SettingsItem(
                title = stringResource(R.string.settings_privacy_policy),
                icon = Icons.Default.PrivacyTip,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToPrivacy) },
            )
            SettingsItem(
                title = stringResource(R.string.settings_terms),
                icon = Icons.AutoMirrored.Filled.ArrowForward,
                onClick = { viewModel.navigateTo(SettingsEvent.NavigateToTerms) },
            )
        }
    }
}
