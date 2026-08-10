package com.safeher.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.settings.components.SettingsCard

@Composable
fun SecurityScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val security = uiState.securityInfo

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SettingsCard {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    SecurityRow(
                        label = stringResource(R.string.settings_security_jwt),
                        value = if (security?.hasJwt == true) {
                            stringResource(R.string.settings_security_active)
                        } else {
                            stringResource(R.string.settings_security_missing)
                        },
                    )
                    SecurityRow(
                        label = stringResource(R.string.settings_security_session),
                        value = if (security?.isSessionActive == true) {
                            stringResource(R.string.settings_security_active)
                        } else {
                            stringResource(R.string.settings_security_inactive)
                        },
                    )
                    SecurityRow(
                        label = stringResource(R.string.settings_security_phone),
                        value = if (security?.isPhoneVerified == true) {
                            stringResource(R.string.status_verified)
                        } else {
                            stringResource(R.string.status_unverified)
                        },
                    )
                    SecurityRow(
                        label = stringResource(R.string.settings_security_version),
                        value = security?.appVersion.orEmpty(),
                    )
                    val backendUrl = security?.backendUrl
                    if (!backendUrl.isNullOrBlank()) {
                        SecurityRow(
                            label = stringResource(R.string.settings_security_backend),
                            value = backendUrl,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SecurityRow(label: String, value: String) {
    Text(text = label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(text = value, style = MaterialTheme.typography.bodyLarge)
}
