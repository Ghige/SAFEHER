package com.safeher.app.feature.settings

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.settings.components.PermissionStatusCard

@Composable
fun PermissionScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    val permissions = uiState.permissionStatuses

    val locationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { viewModel.refreshPermissions() }

    val audioLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { viewModel.refreshPermissions() }

    val notificationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { viewModel.refreshPermissions() }

    DisposableLifecycleEffect(lifecycleOwner, onResume = viewModel::refreshPermissions)

    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (permissions != null) {
                PermissionStatusCard(
                    title = stringResource(R.string.settings_permission_location),
                    status = permissions.location,
                    onRequest = {
                        locationLauncher.launch(
                            arrayOf(
                                Manifest.permission.ACCESS_FINE_LOCATION,
                                Manifest.permission.ACCESS_COARSE_LOCATION,
                            ),
                        )
                    },
                    onOpenSettings = viewModel::openAppSettings,
                )
                PermissionStatusCard(
                    title = stringResource(R.string.settings_permission_microphone),
                    status = permissions.microphone,
                    onRequest = { audioLauncher.launch(Manifest.permission.RECORD_AUDIO) },
                    onOpenSettings = viewModel::openAppSettings,
                )
                PermissionStatusCard(
                    title = stringResource(R.string.settings_permission_notifications),
                    status = permissions.notifications,
                    onRequest = { notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) },
                    onOpenSettings = viewModel::openAppSettings,
                )
                PermissionStatusCard(
                    title = stringResource(R.string.settings_permission_background_location),
                    status = permissions.backgroundLocation,
                    onOpenSettings = viewModel::openAppSettings,
                )
            }
            Button(onClick = viewModel::openAppSettings, modifier = Modifier.fillMaxWidth()) {
                androidx.compose.material3.Text(stringResource(R.string.settings_open_system_settings))
            }
        }
    }
}

@Composable
private fun DisposableLifecycleEffect(
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    onResume: () -> Unit,
) {
    androidx.compose.runtime.DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) onResume()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}
