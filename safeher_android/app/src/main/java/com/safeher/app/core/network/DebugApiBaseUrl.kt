package com.safeher.app.core.network

import android.os.Build
import com.safeher.app.BuildConfig

/**
 * Debug API host selection.
 *
 * - Release: [BuildConfig.BASE_URL] (`https://api.safeher.app/`)
 * - Debug emulator: always `http://10.0.2.2:8000/` (host loopback). LAN override is ignored
 *   so a Pixel/AVD cannot get stuck on a stale machine IP.
 * - Debug physical device with `DEBUG_API_BASE_URL` in local.properties: that LAN URL
 * - Debug physical device without override: [BuildConfig.BASE_URL]
 */
object DebugApiBaseUrl {

    fun resolve(): String = resolve(
        isDebug = BuildConfig.DEBUG,
        emulator = isEmulator(),
        debugDeviceUrl = BuildConfig.BASE_URL,
        debugEmulatorUrl = BuildConfig.EMULATOR_DEBUG_BASE_URL,
        releaseUrl = BuildConfig.BASE_URL,
        debugLanOverride = BuildConfig.DEBUG_API_BASE_URL,
    )

    internal fun resolve(
        isDebug: Boolean,
        emulator: Boolean,
        debugDeviceUrl: String,
        debugEmulatorUrl: String,
        releaseUrl: String,
        debugLanOverride: String = "",
    ): String {
        if (!isDebug) return releaseUrl
        if (emulator) return debugEmulatorUrl.ifBlank { debugDeviceUrl }
        val override = debugLanOverride.trim()
        if (override.isNotEmpty()) return override
        return debugDeviceUrl
    }

    internal fun isEmulator(
        fingerprint: String = Build.FINGERPRINT,
        model: String = Build.MODEL,
        manufacturer: String = Build.MANUFACTURER,
        hardware: String = Build.HARDWARE,
        product: String = Build.PRODUCT,
        device: String = Build.DEVICE,
    ): Boolean {
        val fp = fingerprint.lowercase()
        val modelL = model.lowercase()
        val man = manufacturer.lowercase()
        val hw = hardware.lowercase()
        val prod = product.lowercase()
        val dev = device.lowercase()
        return fp.startsWith("generic") ||
            fp.startsWith("unknown") ||
            "google_sdk" in modelL ||
            "emulator" in modelL ||
            "android sdk built for" in modelL ||
            "genymotion" in man ||
            "goldfish" in hw ||
            "ranchu" in hw ||
            prod.contains("sdk") ||
            "emulator" in prod ||
            "simulator" in prod ||
            "generic" in dev
    }
}
