package com.safeher.app.domain.model

enum class AppThemeMode(val storageKey: String) {
    SYSTEM("system"),
    LIGHT("light"),
    DARK("dark"),
    ;

    companion object {
        fun fromKey(key: String?): AppThemeMode =
            entries.find { it.storageKey == key } ?: SYSTEM
    }
}

enum class AiSensitivity(val storageKey: String, val label: String) {
    LOW("low", "Low"),
    MEDIUM("medium", "Medium"),
    HIGH("high", "High"),
    ;

    companion object {
        fun fromKey(key: String?): AiSensitivity =
            entries.find { it.storageKey == key } ?: MEDIUM
    }
}

enum class PermissionDisplayStatus {
    GRANTED,
    DENIED,
    PERMANENTLY_DENIED,
    NOT_REQUESTED,
}

data class PermissionStatuses(
    val location: PermissionDisplayStatus,
    val microphone: PermissionDisplayStatus,
    val notifications: PermissionDisplayStatus,
    val backgroundLocation: PermissionDisplayStatus,
)

data class SecurityInfo(
    val hasJwt: Boolean,
    val isSessionActive: Boolean,
    val isPhoneVerified: Boolean,
    val appVersion: String,
    val backendUrl: String,
)
