package com.safeher.app.feature.location.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberCameraPositionState
import com.safeher.app.BuildConfig
import com.safeher.app.R

@Composable
fun LocationMap(
    latitude: Double,
    longitude: Double,
    followUser: Boolean,
    myLocationEnabled: Boolean,
    modifier: Modifier = Modifier,
) {
    if (BuildConfig.MAPS_API_KEY.isBlank()) {
        Box(
            modifier = modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = stringResource(R.string.location_maps_unavailable),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    val position = LatLng(latitude, longitude)
    val cameraPositionState = rememberCameraPositionState {
        this.position = CameraPosition.fromLatLngZoom(position, 16f)
    }

    LaunchedEffect(latitude, longitude, followUser) {
        if (followUser) {
            cameraPositionState.animate(
                CameraUpdateFactory.newLatLng(position),
            )
        }
    }

    GoogleMap(
        modifier = modifier,
        cameraPositionState = cameraPositionState,
        properties = MapProperties(isMyLocationEnabled = myLocationEnabled),
        uiSettings = MapUiSettings(
            myLocationButtonEnabled = myLocationEnabled,
            zoomControlsEnabled = true,
        ),
    ) {
        Marker(
            state = MarkerState(position = position),
            title = "Current Location",
        )
    }
}
