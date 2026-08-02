package com.safeher.app.core.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import com.safeher.app.services.NotificationPermissionManager
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@Composable
fun NotificationPermissionEffect(
    viewModel: NotificationPermissionViewModel = hiltViewModel(),
) {
    if (!viewModel.permissionManager.requiresRuntimePermission()) return
    if (viewModel.permissionManager.hasNotificationPermission()) return

    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { /* result handled on next FGS start */ }

    LaunchedEffect(Unit) {
        launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}

@HiltViewModel
class NotificationPermissionViewModel @Inject constructor(
    val permissionManager: NotificationPermissionManager,
) : ViewModel()
