package com.safeher.app.core.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.userPreferencesDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "safeher_user_preferences",
)

@Singleton
class UserPreferences @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val dataStore = context.userPreferencesDataStore

    val onboardingCompleted: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[Keys.ONBOARDING_COMPLETED] ?: false
    }

    val userPhone: Flow<String?> = dataStore.data.map { prefs ->
        prefs[Keys.USER_PHONE]
    }

    val isPhoneVerified: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[Keys.IS_PHONE_VERIFIED] ?: false
    }

    suspend fun setOnboardingCompleted(completed: Boolean) {
        dataStore.edit { prefs ->
            prefs[Keys.ONBOARDING_COMPLETED] = completed
        }
    }

    suspend fun setUserPhone(phone: String) {
        dataStore.edit { prefs ->
            prefs[Keys.USER_PHONE] = phone
        }
    }

    suspend fun setPhoneVerified(verified: Boolean) {
        dataStore.edit { prefs ->
            prefs[Keys.IS_PHONE_VERIFIED] = verified
        }
    }

    suspend fun clear() {
        dataStore.edit { it.clear() }
    }

    private object Keys {
        val ONBOARDING_COMPLETED = booleanPreferencesKey("onboarding_completed")
        val USER_PHONE = stringPreferencesKey("user_phone")
        val IS_PHONE_VERIFIED = booleanPreferencesKey("is_phone_verified")
    }
}
