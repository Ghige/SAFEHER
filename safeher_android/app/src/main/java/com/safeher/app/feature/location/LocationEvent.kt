package com.safeher.app.feature.location

sealed interface LocationEvent {
    data object NavigateToPermission : LocationEvent
    data object NavigateToSettings : LocationEvent
    data object NavigateToTrack : LocationEvent
    data object NavigateBack : LocationEvent
    data class OpenTrackUrl(val url: String) : LocationEvent
}
