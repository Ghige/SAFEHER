package com.safeher.app.feature.location

import android.Manifest
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
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
import com.safeher.app.core.designsystem.components.SafeHerStatusBadge
import com.safeher.app.feature.contacts.ContactsViewModel
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.SafeHerScreenHeader
import com.safeher.app.feature.location.components.CurrentLocationCard
import com.safeher.app.feature.location.components.LoadingLocation
import com.safeher.app.feature.location.components.LocationMap
import com.safeher.app.feature.location.components.PermissionCard
import com.safeher.app.services.LocationPermissionStatus
import kotlinx.coroutines.flow.collectLatest

@Composable
fun LocationScreen(
    onNavigateToPermission: () -> Unit,
    onNavigateToTrack: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: LocationViewModel = hiltViewModel(),
    contactsViewModel: ContactsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val contactsState by contactsViewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { results ->
        val granted = results[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            results[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        viewModel.onPermissionResult(
            granted = granted,
            shouldShowRationale = false,
        )
        if (granted) viewModel.startLocationUpdates()
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            when (event) {
                LocationEvent.NavigateToPermission -> onNavigateToPermission()
                LocationEvent.NavigateToTrack -> onNavigateToTrack()
                is LocationEvent.OpenTrackUrl -> {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(event.url)))
                }
                else -> Unit
            }
        }
    }

    LaunchedEffect(uiState.permissionStatus) {
        if (uiState.permissionStatus == LocationPermissionStatus.GRANTED &&
            uiState.isGpsEnabled
        ) {
            viewModel.startLocationUpdates()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(padding),
        ) {
            SafeHerScreenHeader(
                title = stringResource(R.string.action_live_location),
                actionIcon = SafeHerIcons.More,
                onActionClick = { /* reserved for future actions */ },
            )

            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            when {
                uiState.permissionStatus != LocationPermissionStatus.GRANTED ||
                    !uiState.isGpsEnabled -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                            .verticalScroll(rememberScrollState()),
                    ) {
                        PermissionCard(
                            permissionStatus = uiState.permissionStatus,
                            isGpsEnabled = uiState.isGpsEnabled,
                            onRequestPermission = {
                                permissionLauncher.launch(
                                    arrayOf(
                                        Manifest.permission.ACCESS_FINE_LOCATION,
                                        Manifest.permission.ACCESS_COARSE_LOCATION,
                                    ),
                                )
                            },
                            onOpenAppSettings = viewModel::openAppSettings,
                            onOpenLocationSettings = viewModel::openLocationSettings,
                        )
                    }
                }
                uiState.isLoading && uiState.currentLocation == null -> LoadingLocation()
                uiState.currentLocation != null -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        LocationMap(
                            latitude = uiState.currentLocation!!.latitude,
                            longitude = uiState.currentLocation!!.longitude,
                            followUser = uiState.followUser,
                            myLocationEnabled = true,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(260.dp),
                        )

                        SafeHerCard(modifier = Modifier.fillMaxWidth()) {
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(
                                    text = stringResource(R.string.location_sharing_title),
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                Text(
                                    text = stringResource(
                                        R.string.home_sharing_with_contacts,
                                        contactsState.contacts.size,
                                    ),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = SafeHerTextSecondary,
                                )
                                TextButton(onClick = onNavigateToTrack) {
                                    Text(
                                        text = stringResource(R.string.location_view_on_map),
                                        color = SafeHerPrimary,
                                    )
                                }
                            }
                        }

                        CurrentLocationCard(location = uiState.currentLocation)

                        contactsState.contacts.forEach { contact ->
                            SafeHerCard(modifier = Modifier.fillMaxWidth()) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(44.dp)
                                            .clip(CircleShape)
                                            .background(SafeHerLightPink),
                                        contentAlignment = Alignment.Center,
                                    ) {
                                        Text(
                                            text = contact.name.firstOrNull()?.uppercase() ?: "?",
                                            color = SafeHerPrimary,
                                            style = MaterialTheme.typography.titleSmall,
                                        )
                                    }
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = contact.name,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.SemiBold,
                                        )
                                        Text(
                                            text = contact.phoneNumber,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = SafeHerTextSecondary,
                                        )
                                    }
                                    SafeHerStatusBadge(
                                        text = if (uiState.isTracking) {
                                            stringResource(R.string.status_active)
                                        } else {
                                            stringResource(R.string.status_inactive)
                                        },
                                        isActive = uiState.isTracking,
                                    )
                                }
                            }
                        }

                        if (uiState.activeAlertId != null) {
                            Button(
                                onClick = onNavigateToTrack,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(stringResource(R.string.location_view_tracking))
                            }
                            OutlinedButton(
                                onClick = viewModel::generateTrackLink,
                                modifier = Modifier.fillMaxWidth(),
                                enabled = !uiState.isOffline,
                            ) {
                                Text(stringResource(R.string.location_share_track_link))
                            }
                        }
                        OutlinedButton(
                            onClick = viewModel::loadCurrentLocation,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.action_retry))
                        }
                    }
                }
                else -> {
                    ErrorView(
                        message = uiState.error ?: stringResource(R.string.location_unavailable),
                        onRetry = viewModel::loadCurrentLocation,
                        errorType = if (uiState.isOffline) ErrorType.OFFLINE else ErrorType.NETWORK,
                    )
                }
            }
        }
    }
}
