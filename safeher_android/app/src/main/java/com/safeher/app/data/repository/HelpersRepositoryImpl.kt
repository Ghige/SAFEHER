package com.safeher.app.data.repository

import com.safeher.app.core.network.HelpersApi
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.data.remote.dto.NearbyHelperDto
import com.safeher.app.domain.model.NearbyHelper
import com.safeher.app.domain.repository.HelpersRepository
import com.squareup.moshi.Moshi
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class HelpersRepositoryImpl @Inject constructor(
    private val api: HelpersApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : HelpersRepository {

    override suspend fun getNearbyHelpers(alertId: String): Result<List<NearbyHelper>> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.getNearbyHelpers(alertId).map { it.toDomain() }
        }

    override suspend fun respondToAlert(alertId: String): Result<NearbyHelper> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.respondToAlert(alertId).toDomain()
        }

    override suspend fun blockHelper(helperId: String): Result<Unit> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            val response = api.blockHelper(helperId)
            if (!response.isSuccessful) {
                throw HttpException(response)
            }
            Unit
        }

    private fun NearbyHelperDto.toDomain() = NearbyHelper(
        id = id,
        alertId = alert_id,
        status = status,
        notifiedAt = notified_at,
        identityRevealed = identity_revealed,
        approvedByUser = approved_by_user,
        name = name,
        phoneNumber = phone_number,
    )
}
