package com.safeher.app.domain.repository

import com.safeher.app.domain.model.UserProfile
import kotlinx.coroutines.flow.Flow

interface UserRepository {

    fun observeNetworkStatus(): Flow<Boolean>

    suspend fun getProfile(forceRefresh: Boolean = false): Result<UserProfile>

    suspend fun deleteAccount(): Result<Unit>

    fun clearProfileCache()
}
