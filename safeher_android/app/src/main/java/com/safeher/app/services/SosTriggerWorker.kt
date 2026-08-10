package com.safeher.app.services

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.safeher.app.core.datastore.PendingSosStore
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.core.network.AlertsApi
import com.safeher.app.data.mapper.toSafetyAlert
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import timber.log.Timber
import java.util.concurrent.TimeUnit

@HiltWorker
class SosTriggerWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val pendingSosStore: PendingSosStore,
    private val alertsApi: AlertsApi,
    private val alertSessionManager: AlertSessionManager,
    private val applicationScope: ApplicationCoroutineScope,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val pending = pendingSosStore.getPending() ?: return Result.success()

        return try {
            val dto = alertsApi.triggerAlert(
                com.safeher.app.data.remote.dto.TriggerAlertRequestDto(
                    trigger_type = pending.triggerType,
                    latitude = pending.latitude,
                    longitude = pending.longitude,
                ),
            )
            pendingSosStore.clear()
            activateAlert(dto.toSafetyAlert())
            Result.success()
        } catch (e: Exception) {
            Timber.w(e, "Failed to flush queued SOS")
            if (runAttemptCount < MAX_RETRIES) {
                Result.retry()
            } else {
                Result.failure()
            }
        }
    }

    private suspend fun activateAlert(alert: com.safeher.app.domain.model.SafetyAlert) {
        alertSessionManager.setActiveAlert(alert)
        alertSessionManager.startHeartbeat(alert.id, applicationScope.scope)
    }

    companion object {
        private const val WORK_NAME = "sos_trigger_flush"
        private const val MAX_RETRIES = 5

        fun enqueueFlush(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<SosTriggerWorker>()
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
