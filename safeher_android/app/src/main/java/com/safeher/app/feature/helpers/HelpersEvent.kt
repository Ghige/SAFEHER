package com.safeher.app.feature.helpers

import com.safeher.app.domain.model.NearbyHelper

sealed interface HelpersEvent {
    data class NavigateToProfile(val helperId: String) : HelpersEvent
    data object NavigateToBlocked : HelpersEvent
}

enum class HelperResponseAction {
    ACCEPT,
    DECLINE,
}
