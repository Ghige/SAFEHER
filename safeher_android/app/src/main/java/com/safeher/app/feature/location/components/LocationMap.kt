package com.safeher.app.feature.location.components

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberCameraPositionState

@Composable
fun LocationMap(
    latitude: Double,
    longitude: Double,
    followUser: Boolean,
    myLocationEnabled: Boolean,
    modifier: Modifier = Modifier,
) {
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
