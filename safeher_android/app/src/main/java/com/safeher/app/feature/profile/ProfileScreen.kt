package com.safeher.app.feature.profile

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.ProfileDetailRow
import com.safeher.app.feature.home.components.ProfileLoadingView
import com.safeher.app.feature.home.components.VerificationBadge
import kotlinx.coroutines.flow.collectLatest

@Composable
fun ProfileScreen(
    onNavigateToLogin: () -> Unit,
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
            )
        }
    }
}

@Composable
private fun ProfileContent(
    uiState: ProfileUiState,
    onLogout: () -> Unit,
) {
    val profile = uiState.profile ?: return

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Text(
            text = stringResource(R.string.profile_title),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(modifier = Modifier.height(20.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = MaterialTheme.shapes.large,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
            ),
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                ProfileDetailRow(
                    label = stringResource(R.string.field_name),
                    value = profile.name,
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                ProfileDetailRow(
                    label = stringResource(R.string.field_phone),
                    value = profile.phoneNumber,
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                ProfileDetailRow(
                    label = stringResource(R.string.field_city),
                    value = profile.city?.takeIf { it.isNotBlank() }
                        ?: stringResource(R.string.profile_city_not_set),
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                Column(modifier = Modifier.padding(vertical = 8.dp)) {
                    Text(
                        text = stringResource(R.string.profile_verification),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    VerificationBadge(isVerified = profile.isVerified, onContainer = false)
                }
            }
        }

        Spacer(modifier = Modifier.weight(1f))

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
