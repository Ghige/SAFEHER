package com.safeher.app.data.repository

import com.safeher.app.core.datastore.PendingSosRequest
import com.safeher.app.core.datastore.PendingSosStore
import com.safeher.app.core.network.AlertsApi
import com.safeher.app.core.network.ApiErrorParser
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.RepositoryApiCall
import com.safeher.app.core.network.RetrofitDiagnostics
import com.safeher.app.data.mapper.toSafetyAlert
import com.safeher.app.data.remote.dto.TriggerAlertRequestDto
import com.safeher.app.domain.model.SafetyAlert
import com.safeher.app.domain.repository.AlertRepository
import com.safeher.app.services.SosTriggerScheduler
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertRepositoryImpl @Inject constructor(
    private val api: AlertsApi,
    private val networkMonitor: NetworkMonitor,
    private val moshi: Moshi,
    private val pendingSosStore: PendingSosStore,
    private val sosTriggerScheduler: SosTriggerScheduler,
) : AlertRepository {

    override fun observePendingSos(): Flow<Boolean> = pendingSosStore.hasPending

    override suspend fun triggerAlert(latitude: Double?, longitude: Double?): Result<SafetyAlert> {
        if (!networkMonitor.isOnline.first()) {
            return queueOfflineTrigger(latitude, longitude)
        }
        return triggerAlertOnline(latitude, longitude)
    }

    override suspend fun cancelAlert(alertId: String): Result<SafetyAlert> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.cancelAlert(alertId).toSafetyAlert()
        }

    override suspend fun pingAlert(alertId: String): Result<Unit> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.pingAlert(alertId)
            Unit
        }

    override suspend fun getActiveAlert(): Result<SafetyAlert?> {
        val path = "api/v1/alerts/active"
        RetrofitDiagnostics.logRequest(TAG, "GET", path)
        return try {
            Timber.d("%s: awaiting networkMonitor.isOnline.first()", TAG)
            val isOnline = networkMonitor.isOnline.first()
            Timber.d("%s: networkMonitor.isOnline.first()=%s", TAG, isOnline)
            if (!isOnline) {
                RetrofitDiagnostics.logOfflineGate(TAG, path, isOnline)
                return Result.failure(Exception("You are offline. Connect to the internet and try again."))
            }
            Timber.d("%s: invoking Retrofit GET %s", TAG, path)
            val alert = api.getActiveAlert().toSafetyAlert()
            RetrofitDiagnostics.logSuccess(TAG, path)
            Result.success(alert)
        } catch (e: HttpException) {
            RetrofitDiagnostics.logFailure(TAG, path, e)
            if (e.code() == 404) {
                Timber.d("%s: GET %s returned 404 — no active alert", TAG, path)
                Result.success(null)
            } else {
                Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
            }
        } catch (e: Exception) {
            RetrofitDiagnostics.logFailure(TAG, path, e)
            Result.failure(Exception(ApiErrorParser.parse(e, moshi)))
        }
    }

    override suspend fun getHistory(): Result<List<SafetyAlert>> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            api.getHistory().map { it.toSafetyAlert() }
        }

    private suspend fun queueOfflineTrigger(latitude: Double?, longitude: Double?): Result<SafetyAlert> {
        val hasLat = latitude != null
        val hasLon = longitude != null
        if (hasLat xor hasLon) {
            return Result.failure(
                IllegalArgumentException("latitude and longitude must both be provided or both omitted"),
            )
        }
        pendingSosStore.save(
            PendingSosRequest(
                latitude = latitude,
                longitude = longitude,
                triggerType = TRIGGER_TYPE_MANUAL,
                queuedAtEpochMs = System.currentTimeMillis(),
            ),
        )
        sosTriggerScheduler.scheduleFlush()
        return Result.failure(OfflineSosQueuedException())
    }

    private suspend fun triggerAlertOnline(latitude: Double?, longitude: Double?): Result<SafetyAlert> =
        RepositoryApiCall.executeOnline(moshi, networkMonitor) {
            val hasLat = latitude != null
            val hasLon = longitude != null
            val (lat, lon) = when {
                hasLat && hasLon -> latitude to longitude
                !hasLat && !hasLon -> null to null
                else -> throw IllegalArgumentException(
                    "latitude and longitude must both be provided or both omitted",
                )
            }
            api.triggerAlert(
                TriggerAlertRequestDto(
                    trigger_type = TRIGGER_TYPE_MANUAL,
                    latitude = lat,
                    longitude = lon,
                ),
            ).toSafetyAlert()
        }

    companion object {
        private const val TAG = "AlertRepositoryImpl"
        const val TRIGGER_TYPE_MANUAL = "manual"
    }
}
