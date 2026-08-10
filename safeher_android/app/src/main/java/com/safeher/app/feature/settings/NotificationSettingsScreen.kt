package com.safeher.app.feature.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.settings.components.SettingsCard
import com.safeher.app.feature.settings.components.TogglePreference

@Composable
fun NotificationSettingsScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
        ) {
            SettingsCard {
                TogglePreference(
                    title = stringResource(R.string.settings_notifications_enable),
                    checked = uiState.notificationsEnabled,
                    onCheckedChange = viewModel::setNotificationsEnabled,
                )
                TogglePreference(
                    title = stringResource(R.string.settings_notifications_sos),
                    subtitle = stringResource(R.string.settings_notifications_sos_desc),
                    checked = uiState.sosNotificationsEnabled,
                    onCheckedChange = viewModel::setSosNotificationsEnabled,
                    enabled = uiState.notificationsEnabled,
                )
                TogglePreference(
                    title = stringResource(R.string.settings_notifications_helpers),
                    subtitle = stringResource(R.string.settings_notifications_helpers_desc),
                    checked = uiState.helperNotificationsEnabled,
                    onCheckedChange = viewModel::setHelperNotificationsEnabled,
                    enabled = uiState.notificationsEnabled,
                )
                TogglePreference(
                    title = stringResource(R.string.settings_notifications_ai),
                    subtitle = stringResource(R.string.settings_notifications_ai_desc),
                    checked = uiState.aiNotificationsEnabled,
                    onCheckedChange = viewModel::setAiNotificationsEnabled,
                    enabled = uiState.notificationsEnabled,
                )
            }
        }
    }
}
