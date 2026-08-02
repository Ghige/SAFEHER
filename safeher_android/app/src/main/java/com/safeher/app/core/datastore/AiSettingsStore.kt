package com.safeher.app.core.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.aiSettingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "safeher_ai_settings",
)

@Singleton
class AiSettingsStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.aiSettingsDataStore

    val monitoringEnabled: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[Keys.MONITORING_ENABLED] ?: false
    }

    val isIsolated: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[Keys.IS_ISOLATED] ?: false
    }

    suspend fun setMonitoringEnabled(enabled: Boolean) {
        dataStore.edit { prefs ->
            prefs[Keys.MONITORING_ENABLED] = enabled
        }
    }

    suspend fun setIsIsolated(isolated: Boolean) {
        dataStore.edit { prefs ->
            prefs[Keys.IS_ISOLATED] = isolated
        }
    }

    private object Keys {
        val MONITORING_ENABLED = booleanPreferencesKey("ai_monitoring_enabled")
        val IS_ISOLATED = booleanPreferencesKey("ai_is_isolated")
    }
}
