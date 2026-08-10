package com.safeher.app.services

import android.content.Context
import android.content.Intent
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.repository.LocationRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.util.concurrent.TimeUnit

@HiltWorker
class LocationWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val locationRepository: LocationRepository,
    private val alertSessionManager: AlertSessionManager,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val alertId = inputData.getString(KEY_ALERT_ID) ?: return Result.failure()
        val latitude = inputData.getDouble(KEY_LATITUDE, Double.NaN)
        val longitude = inputData.getDouble(KEY_LONGITUDE, Double.NaN)
        if (latitude.isNaN() || longitude.isNaN()) return Result.failure()

        val alert = alertSessionManager.activeAlert.value
        if (alert == null || !alert.isOngoing || alert.id != alertId) {
            return Result.success()
        }

        return locationRepository.updateLocation(alertId, latitude, longitude).fold(
            onSuccess = { Result.success() },
            onFailure = {
                if (runAttemptCount < MAX_RETRIES) {
                    Result.retry()
                } else {
                    Result.failure()
                }
            },
        )
    }

    companion object {
        private const val KEY_ALERT_ID = "alert_id"
        private const val KEY_LATITUDE = "latitude"
        private const val KEY_LONGITUDE = "longitude"
        private const val MAX_RETRIES = 3
        private const val WORK_NAME = "location_update_retry"

        fun enqueueRetry(context: Context, alertId: String, latitude: Double, longitude: Double) {
            val data = Data.Builder()
                .putString(KEY_ALERT_ID, alertId)
                .putDouble(KEY_LATITUDE, latitude)
                .putDouble(KEY_LONGITUDE, longitude)
                .build()
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<LocationWorker>()
                .setInputData(data)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                ExistingWorkPolicy.REPLACE,
                request,
            )
        }
    }
}
