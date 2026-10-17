package com.safeher.app.core.network

import com.safeher.app.BuildConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DebugApiBaseUrlTest {

    @Test
    fun debugBuildConfig_emulatorFallbackIsHostLoopback() {
        assertTrue(BuildConfig.DEBUG)
        assertEquals("http://10.0.2.2:8000/", BuildConfig.EMULATOR_DEBUG_BASE_URL)
        assertFalse(BuildConfig.BASE_URL.contains("api.safeher.app"))
    }

    @Test
    fun lanOverride_usedOnPhysicalDevice() {
        val url = DebugApiBaseUrl.resolve(
            isDebug = true,
            emulator = false,
            debugDeviceUrl = "http://10.0.2.2:8000/",
            debugEmulatorUrl = "http://10.0.2.2:8000/",
            releaseUrl = "https://api.safeher.app/",
            debugLanOverride = "http://192.168.1.10:8000/",
        )
        assertEquals("http://192.168.1.10:8000/", url)
    }

    @Test
    fun emulatorUses1022_evenWithLanOverride() {
        val url = DebugApiBaseUrl.resolve(
            isDebug = true,
            emulator = true,
            debugDeviceUrl = "http://10.0.2.2:8000/",
            debugEmulatorUrl = "http://10.0.2.2:8000/",
            releaseUrl = "https://api.safeher.app/",
            debugLanOverride = "http://192.168.1.10:8000/",
        )
        assertEquals("http://10.0.2.2:8000/", url)
    }

    @Test
    fun withoutOverride_emulatorUses1022() {
        val url = DebugApiBaseUrl.resolve(
            isDebug = true,
            emulator = true,
            debugDeviceUrl = "http://10.0.2.2:8000/",
            debugEmulatorUrl = "http://10.0.2.2:8000/",
            releaseUrl = "https://api.safeher.app/",
            debugLanOverride = "",
        )
        assertEquals("http://10.0.2.2:8000/", url)
    }

    @Test
    fun release_ignoresLanOverride() {
        val url = DebugApiBaseUrl.resolve(
            isDebug = false,
            emulator = false,
            debugDeviceUrl = "http://10.0.2.2:8000/",
            debugEmulatorUrl = "http://10.0.2.2:8000/",
            releaseUrl = "https://api.safeher.app/",
            debugLanOverride = "http://192.168.1.10:8000/",
        )
        assertEquals("https://api.safeher.app/", url)
    }

    @Test
    fun isEmulator_detectsSdkFingerprint() {
        assertTrue(
            DebugApiBaseUrl.isEmulator(
                fingerprint = "generic/sdk_gphone64_x86_64/emu64xa:14/test",
                model = "sdk_gphone64_x86_64",
                manufacturer = "Google",
                hardware = "ranchu",
                product = "sdk_gphone64_x86_64",
                device = "emu64xa",
            ),
        )
        assertFalse(
            DebugApiBaseUrl.isEmulator(
                fingerprint = "vivo/iQOO10R/iQOO10R:14/release-keys",
                model = "I2217",
                manufacturer = "vivo",
                hardware = "qcom",
                product = "iQOO10R",
                device = "iQOO10R",
            ),
        )
    }
}
