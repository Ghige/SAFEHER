package com.safeher.app.data.repository

import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.SafeHerApi
import com.safeher.app.domain.model.UserProfile
import com.safeher.app.domain.repository.UserRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserRepositoryImpl @Inject constructor(
    private val api: SafeHerApi,
    private val userPreferences: UserPreferences,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : UserRepository {

    override fun observeNetworkStatus(): Flow<Boolean> = networkMonitor.isOnline

    override suspend fun getProfile(): Result<UserProfile> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                Result.failure(Exception("You are offline. Connect to the internet and try again."))
            } else {
                val dto = api.getProfile()
                if (dto.name.isBlank()) {
                    Result.failure(Exception("Profile data is incomplete."))
                } else {
                    val isVerified = userPreferences.isPhoneVerified.first()
                    Result.success(
                        UserProfile(
                            id = dto.id,
                            phoneNumber = dto.phone_number,
                            name = dto.name,
                            city = dto.city,
                            isVerified = isVerified,
                        ),
                    )
                }
            }
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }
}
