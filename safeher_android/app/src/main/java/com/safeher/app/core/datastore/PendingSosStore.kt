package com.safeher.app.core.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.doublePreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

data class PendingSosRequest(
    val latitude: Double?,
    val longitude: Double?,
    val triggerType: String,
    val queuedAtEpochMs: Long,
)

private val Context.pendingSosDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "safeher_pending_sos",
)

@Singleton
class PendingSosStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val dataStore = context.pendingSosDataStore

    val hasPending: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[Keys.TRIGGER_TYPE] != null
    }

    val pendingRequest: Flow<PendingSosRequest?> = dataStore.data.map { prefs ->
        val triggerType = prefs[Keys.TRIGGER_TYPE] ?: return@map null
        PendingSosRequest(
            latitude = prefs[Keys.LATITUDE],
            longitude = prefs[Keys.LONGITUDE],
            triggerType = triggerType,
            queuedAtEpochMs = prefs[Keys.QUEUED_AT] ?: 0L,
        )
    }

    suspend fun save(request: PendingSosRequest) {
        dataStore.edit { prefs ->
            prefs[Keys.TRIGGER_TYPE] = request.triggerType
            prefs[Keys.QUEUED_AT] = request.queuedAtEpochMs
            if (request.latitude != null && request.longitude != null) {
                prefs[Keys.LATITUDE] = request.latitude
                prefs[Keys.LONGITUDE] = request.longitude
            } else {
                prefs.remove(Keys.LATITUDE)
                prefs.remove(Keys.LONGITUDE)
            }
        }
    }

    suspend fun clear() {
        dataStore.edit { prefs ->
            prefs.remove(Keys.TRIGGER_TYPE)
            prefs.remove(Keys.LATITUDE)
            prefs.remove(Keys.LONGITUDE)
            prefs.remove(Keys.QUEUED_AT)
        }
    }

    suspend fun getPending(): PendingSosRequest? = pendingRequest.first()

    private object Keys {
        val TRIGGER_TYPE = stringPreferencesKey("trigger_type")
        val LATITUDE = doublePreferencesKey("latitude")
        val LONGITUDE = doublePreferencesKey("longitude")
        val QUEUED_AT = longPreferencesKey("queued_at")
    }
}
