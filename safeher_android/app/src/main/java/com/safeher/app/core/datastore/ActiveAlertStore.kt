package com.safeher.app.core.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.activeAlertDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "safeher_active_alert",
)

@Singleton
class ActiveAlertStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val dataStore = context.activeAlertDataStore

    val activeAlertId: Flow<String?> = dataStore.data.map { prefs ->
        prefs[Keys.ALERT_ID]
    }

    suspend fun saveActiveAlertId(alertId: String) {
        dataStore.edit { prefs ->
            prefs[Keys.ALERT_ID] = alertId
        }
    }

    suspend fun clearActiveAlertId() {
        dataStore.edit { prefs ->
            prefs.remove(Keys.ALERT_ID)
        }
    }

    private object Keys {
        val ALERT_ID = stringPreferencesKey("active_alert_id")
    }
}
