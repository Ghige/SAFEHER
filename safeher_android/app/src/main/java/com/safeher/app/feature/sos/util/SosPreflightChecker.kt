package com.safeher.app.feature.sos.util

import com.safeher.app.services.BatteryOptimizationManager
import com.safeher.app.services.LocationPermissionManager
import javax.inject.Inject
import javax.inject.Singleton

enum class SosPreflightCheck {
    LOCATION_PERMISSION,
    GPS_ENABLED,
    BACKGROUND_LOCATION,
    BATTERY_OPTIMIZATION,
}

enum class SosPreflightStatus {
    OK,
    WARNING,
}

data class SosPreflightItem(
    val check: SosPreflightCheck,
    val status: SosPreflightStatus,
)

data class SosPreflightResult(
    val items: List<SosPreflightItem>,
    val locationAvailable: Boolean,
) {
    val allRecommendedMet: Boolean = items.all { it.status == SosPreflightStatus.OK }
    val warningCount: Int = items.count { it.status == SosPreflightStatus.WARNING }
}

@Singleton
class SosPreflightChecker @Inject constructor(
    private val locationPermissionManager: LocationPermissionManager,
    private val batteryOptimizationManager: BatteryOptimizationManager,
) {

    fun evaluate(): SosPreflightResult {
        val hasLocation = locationPermissionManager.hasLocationPermission()
        val gpsEnabled = locationPermissionManager.isGpsEnabled()
        val hasBackground = locationPermissionManager.hasBackgroundLocationPermission()
        val batteryOk = batteryOptimizationManager.isIgnoringBatteryOptimizations()

        val items = listOf(
            SosPreflightItem(
                check = SosPreflightCheck.LOCATION_PERMISSION,
                status = if (hasLocation) SosPreflightStatus.OK else SosPreflightStatus.WARNING,
            ),
            SosPreflightItem(
                check = SosPreflightCheck.GPS_ENABLED,
                status = if (gpsEnabled) SosPreflightStatus.OK else SosPreflightStatus.WARNING,
            ),
            SosPreflightItem(
                check = SosPreflightCheck.BACKGROUND_LOCATION,
                status = if (hasBackground) SosPreflightStatus.OK else SosPreflightStatus.WARNING,
            ),
            SosPreflightItem(
                check = SosPreflightCheck.BATTERY_OPTIMIZATION,
                status = if (batteryOk) SosPreflightStatus.OK else SosPreflightStatus.WARNING,
            ),
        )

        return SosPreflightResult(
            items = items,
            locationAvailable = hasLocation && gpsEnabled,
        )
    }
}
