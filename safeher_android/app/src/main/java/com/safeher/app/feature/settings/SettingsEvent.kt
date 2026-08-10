package com.safeher.app.feature.settings

sealed interface SettingsEvent {
    data object NavigateToPermissions : SettingsEvent
    data object NavigateToNotifications : SettingsEvent
    data object NavigateToSecurity : SettingsEvent
    data object NavigateToAbout : SettingsEvent
    data object NavigateToPrivacy : SettingsEvent
    data object NavigateToTerms : SettingsEvent
    data object NavigateToBattery : SettingsEvent
    data object NavigateToProfile : SettingsEvent
    data object NavigateToLogin : SettingsEvent
    data object OpenAppSettings : SettingsEvent
}
