package com.safeher.app.core.ui.navigation

object Route {
    const val SPLASH = "splash"
    const val ONBOARDING = "onboarding"
    const val LOGIN = "login"
    const val REGISTER = "register"
    const val OTP = "otp/{phone}"
    const val SESSION_EXPIRED = "session_expired"
    const val HOME = "home"
    const val CONTACTS = "contacts"
    const val ADD_CONTACT = "contacts/add"
    const val SOS = "sos"
    const val SOS_COUNTDOWN = "sos/countdown"
    const val SOS_ACTIVE = "sos/active"
    const val SOS_HISTORY = "sos/history"
    const val LOCATION = "location"
    const val LOCATION_PERMISSION = "location/permission"
    const val LOCATION_SETTINGS = "location/settings"
    const val LOCATION_TRACK = "location/track"
    const val HELPERS = "helpers"
    const val HELPER_PROFILE = "helpers/profile/{helper_id}"
    const val HELPERS_BLOCKED = "helpers/blocked"
    const val AI = "ai"
    const val AI_STATUS = "ai/status"
    const val AI_SETTINGS = "ai/settings"
    const val COMING_SOON = "coming_soon/{feature}"

    /** @deprecated Use [HOME] */
    const val PLACEHOLDER = HOME

    const val PHONE_ARG = "phone"
    const val FEATURE_ARG = "feature"
    const val HELPER_ID_ARG = "helper_id"

    fun otp(phone: String): String = "otp/$phone"

    fun comingSoon(feature: String): String = "coming_soon/$feature"

    fun helperProfile(helperId: String): String = "helpers/profile/$helperId"
}
