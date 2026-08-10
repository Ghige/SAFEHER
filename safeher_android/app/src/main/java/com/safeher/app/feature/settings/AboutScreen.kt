package com.safeher.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.settings.components.SettingsCard
import com.safeher.app.feature.settings.components.SettingsItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(
    onNavigateToPrivacy: () -> Unit,
    onNavigateToTerms: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    var showLicenses by rememberSaveable { mutableStateOf(false) }
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val security = uiState.securityInfo

    if (showLicenses) {
        Scaffold(
            modifier = Modifier.padding(contentPadding),
            topBar = {
                TopAppBar(
                    title = { Text(stringResource(R.string.settings_about_licenses)) },
                    navigationIcon = {
                        IconButton(onClick = { showLicenses = false }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = null,
                            )
                        }
                    },
                )
            },
        ) { innerPadding ->
            OpenSourceLicensesScreen(contentPadding = innerPadding)
        }
        return
    }

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SettingsCard {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = stringResource(R.string.app_name),
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        text = stringResource(R.string.settings_about_version, security?.appVersion.orEmpty()),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        text = stringResource(R.string.settings_about_developer),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            SettingsCard {
                SettingsItem(
                    title = stringResource(R.string.settings_privacy_policy),
                    onClick = onNavigateToPrivacy,
                )
                SettingsItem(
                    title = stringResource(R.string.settings_terms),
                    onClick = onNavigateToTerms,
                )
                SettingsItem(
                    title = stringResource(R.string.settings_about_licenses),
                    subtitle = stringResource(R.string.settings_about_licenses_desc),
                    onClick = { showLicenses = true },
                )
            }
        }
    }
}
