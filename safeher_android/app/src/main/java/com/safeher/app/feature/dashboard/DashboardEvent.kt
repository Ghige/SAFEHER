package com.safeher.app.feature.dashboard

sealed interface DashboardEvent {
    data class NavigateToComingSoon(val feature: String) : DashboardEvent
}

enum class QuickActionFeature(val routeKey: String, val titleRes: Int) {
    CONTACTS("contacts", com.safeher.app.R.string.action_contacts),
    SOS("sos", com.safeher.app.R.string.action_sos),
    AI("ai", com.safeher.app.R.string.action_ai),
    HELPERS("helpers", com.safeher.app.R.string.action_helpers),
    LIVE_LOCATION("live_location", com.safeher.app.R.string.action_live_location),
    SETTINGS("settings", com.safeher.app.R.string.action_settings),
}
