package com.safeher.app.domain.repository

import com.safeher.app.domain.model.NearbyHelper

interface HelpersRepository {

    suspend fun getNearbyHelpers(alertId: String): Result<List<NearbyHelper>>

    suspend fun respondToAlert(alertId: String): Result<NearbyHelper>

    suspend fun blockHelper(helperId: String): Result<Unit>
}
