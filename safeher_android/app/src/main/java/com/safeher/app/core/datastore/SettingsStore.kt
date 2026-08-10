package com.safeher.app.core.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.safeher.app.domain.model.AiSensitivity
import com.safeher.app.domain.model.AppThemeMode
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "safeher_settings",
)

@Singleton
class SettingsStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.settingsDataStore

    val notificationsEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.NOTIFICATIONS_ENABLED] ?: true }
    val sosNotificationsEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.SOS_NOTIFICATIONS] ?: true }
    val helperNotificationsEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.HELPER_NOTIFICATIONS] ?: true }
    val aiNotificationsEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.AI_NOTIFICATIONS] ?: true }

    val aiAudioDetectionEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.AI_AUDIO_DETECTION] ?: true }
    val aiMovementDetectionEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.AI_MOVEMENT_DETECTION] ?: true }
    val aiSensitivity: Flow<AiSensitivity> = dataStore.data.map {
        AiSensitivity.fromKey(it[Keys.AI_SENSITIVITY])
    }
    val aiHelpImproveEnabled: Flow<Boolean> = dataStore.data.map { it[Keys.AI_HELP_IMPROVE] ?: false }

    val themeMode: Flow<AppThemeMode> = dataStore.data.map {
        AppThemeMode.fromKey(it[Keys.THEME_MODE])
    }

    val language: Flow<String> = dataStore.data.map { it[Keys.LANGUAGE] ?: "en" }

    suspend fun setNotificationsEnabled(enabled: Boolean) = edit(Keys.NOTIFICATIONS_ENABLED, enabled)
    suspend fun setSosNotificationsEnabled(enabled: Boolean) = edit(Keys.SOS_NOTIFICATIONS, enabled)
    suspend fun setHelperNotificationsEnabled(enabled: Boolean) = edit(Keys.HELPER_NOTIFICATIONS, enabled)
    suspend fun setAiNotificationsEnabled(enabled: Boolean) = edit(Keys.AI_NOTIFICATIONS, enabled)

    suspend fun setAiAudioDetectionEnabled(enabled: Boolean) = edit(Keys.AI_AUDIO_DETECTION, enabled)
    suspend fun setAiMovementDetectionEnabled(enabled: Boolean) = edit(Keys.AI_MOVEMENT_DETECTION, enabled)
    suspend fun setAiSensitivity(sensitivity: AiSensitivity) {
        dataStore.edit { it[Keys.AI_SENSITIVITY] = sensitivity.storageKey }
    }

    suspend fun setAiHelpImproveEnabled(enabled: Boolean) = edit(Keys.AI_HELP_IMPROVE, enabled)

    suspend fun setThemeMode(mode: AppThemeMode) {
        dataStore.edit { it[Keys.THEME_MODE] = mode.storageKey }
    }

    suspend fun setLanguage(languageCode: String) {
        dataStore.edit { it[Keys.LANGUAGE] = languageCode }
    }

    private suspend fun edit(key: Preferences.Key<Boolean>, value: Boolean) {
        dataStore.edit { it[key] = value }
    }

    object Keys {
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val SOS_NOTIFICATIONS = booleanPreferencesKey("sos_notifications")
        val HELPER_NOTIFICATIONS = booleanPreferencesKey("helper_notifications")
        val AI_NOTIFICATIONS = booleanPreferencesKey("ai_notifications")
        val AI_AUDIO_DETECTION = booleanPreferencesKey("ai_audio_detection")
        val AI_MOVEMENT_DETECTION = booleanPreferencesKey("ai_movement_detection")
        val AI_SENSITIVITY = stringPreferencesKey("ai_sensitivity")
        val AI_HELP_IMPROVE = booleanPreferencesKey("ai_help_improve")
        val THEME_MODE = stringPreferencesKey("theme_mode")
        val LANGUAGE = stringPreferencesKey("language")
    }
}
