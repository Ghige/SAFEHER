package com.safeher.app.data.repository

import com.safeher.app.core.network.AlertsApi
import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.data.remote.dto.AlertResponseDto
import com.safeher.app.data.remote.dto.TriggerAlertRequestDto
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertRepositoryImpl @Inject constructor(
    private val api: AlertsApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
) : AlertRepository {

    override suspend fun triggerAlert(latitude: Double?, longitude: Double?): Result<SafetyAlert> {
        return apiCall {
            val hasLat = latitude != null
            val hasLon = longitude != null
            val (lat, lon) = when {
                hasLat && hasLon -> latitude to longitude
                !hasLat && !hasLon -> null to null
                else -> throw IllegalArgumentException("latitude and longitude must both be provided or both omitted")
            }
            api.triggerAlert(
                TriggerAlertRequestDto(
                    trigger_type = TRIGGER_TYPE_MANUAL,
                    latitude = lat,
                    longitude = lon,
                ),
            ).toDomain()
        }
    }

    override suspend fun cancelAlert(alertId: String): Result<SafetyAlert> = apiCall {
        api.cancelAlert(alertId).toDomain()
    }

    override suspend fun pingAlert(alertId: String): Result<Unit> = apiCall {
        api.pingAlert(alertId)
        Unit
    }

    override suspend fun getActiveAlert(): Result<SafetyAlert?> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                return Result.failure(Exception("You are offline. Connect to the internet and try again."))
            }
            Result.success(api.getActiveAlert().toDomain())
        } catch (e: HttpException) {
            if (e.code() == 404) {
                Result.success(null)
            } else {
                Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }

    override suspend fun getHistory(): Result<List<SafetyAlert>> = apiCall {
        api.getHistory().map { it.toDomain() }
    }

    private suspend inline fun <T> apiCall(block: () -> T): Result<T> {
        return try {
            if (!networkMonitor.isOnline.first()) {
                Result.failure(Exception("You are offline. Connect to the internet and try again."))
            } else {
                Result.success(block())
            }
        } catch (e: Exception) {
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }

    private fun AlertResponseDto.toDomain() = SafetyAlert(
        id = id,
        triggerType = trigger_type,
        latitude = latitude,
        longitude = longitude,
        status = status,
        startedAt = started_at,
        endedAt = ended_at,
        evidenceUrl = evidence_url,
    )

    companion object {
        const val TRIGGER_TYPE_MANUAL = "manual"
    }
}
