package com.safeher.app.feature.ai

sealed interface AiMonitoringEvent {
    data object NavigateToSosCountdown : AiMonitoringEvent
    data object NavigateToActiveAlert : AiMonitoringEvent
    data object NavigateToStatus : AiMonitoringEvent
    data object NavigateToSettings : AiMonitoringEvent
    data object RequestAudioPermission : AiMonitoringEvent
}
