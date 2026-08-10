package com.safeher.app.core.datastore

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureTokenStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        PREFS_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    @Volatile
    private var cachedToken: String? = prefs.getString(KEY_ACCESS_TOKEN, null)

    fun getAccessTokenSync(): String? = cachedToken

    suspend fun saveAccessToken(token: String) {
        prefs.edit().putString(KEY_ACCESS_TOKEN, token).commit()
        cachedToken = token
    }

    suspend fun getAccessToken(): String? {
        cachedToken?.let { return it }
        return prefs.getString(KEY_ACCESS_TOKEN, null)?.also { cachedToken = it }
    }

    suspend fun clear() {
        prefs.edit().remove(KEY_ACCESS_TOKEN).commit()
        cachedToken = null
    }

    companion object {
        private const val PREFS_NAME = "safeher_secure_tokens"
        private const val KEY_ACCESS_TOKEN = "access_token"
    }
}
