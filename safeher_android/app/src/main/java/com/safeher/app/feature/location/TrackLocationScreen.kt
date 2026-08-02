package com.safeher.app.feature.location

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.location.components.CurrentLocationCard
import com.safeher.app.feature.location.components.LoadingLocation
import com.safeher.app.feature.location.components.LocationMap
import com.safeher.app.feature.location.components.TrackingStatusChip
import kotlinx.coroutines.flow.collectLatest

@Composable
fun TrackLocationScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: LocationViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.startLocationUpdates()
    }

    LaunchedEffect(Unit) {
        viewModel.events.collectLatest { event ->
            if (event is LocationEvent.OpenTrackUrl) {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(event.url)))
            }
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
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            Text(
                text = stringResource(R.string.location_track_title),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            TrackingStatusChip(isTracking = uiState.isTracking)

            when {
                uiState.activeAlertId == null -> {
                    Text(
                        text = stringResource(R.string.location_no_active_alert),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                uiState.isLoading && uiState.currentLocation == null -> LoadingLocation()
                uiState.currentLocation != null -> {
                    LocationMap(
                        latitude = uiState.currentLocation!!.latitude,
                        longitude = uiState.currentLocation!!.longitude,
                        followUser = true,
                        myLocationEnabled = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(300.dp),
                    )
                    CurrentLocationCard(location = uiState.currentLocation)
                    Button(
                        onClick = viewModel::generateTrackLink,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !uiState.isOffline && uiState.activeAlertId != null,
                    ) {
                        Text(stringResource(R.string.location_share_track_link))
                    }
                    uiState.trackUrl?.let { url ->
                        OutlinedButton(
                            onClick = {
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.location_open_track_link))
                        }
                    }
                }
                else -> LoadingLocation()
            }
        }
    }
}
