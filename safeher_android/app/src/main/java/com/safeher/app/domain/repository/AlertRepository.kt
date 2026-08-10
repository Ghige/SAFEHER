package com.safeher.app.domain.repository

import com.safeher.app.domain.model.SafetyAlert
import kotlinx.coroutines.flow.Flow

interface AlertRepository {

    fun observePendingSos(): Flow<Boolean>

    suspend fun triggerAlert(latitude: Double?, longitude: Double?): Result<SafetyAlert>

    suspend fun cancelAlert(alertId: String): Result<SafetyAlert>

    suspend fun pingAlert(alertId: String): Result<Unit>

    suspend fun getActiveAlert(): Result<SafetyAlert?>

    suspend fun getHistory(): Result<List<SafetyAlert>>
}
