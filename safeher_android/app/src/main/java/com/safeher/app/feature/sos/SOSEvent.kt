package com.safeher.app.feature.sos

sealed interface SOSEvent {
    data object NavigateToCountdown : SOSEvent
    data object NavigateToActive : SOSEvent
    data object NavigateToHistory : SOSEvent
    data object NavigateBack : SOSEvent
}
