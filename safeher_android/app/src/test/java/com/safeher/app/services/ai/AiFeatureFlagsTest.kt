package com.safeher.app.services.ai

import com.safeher.app.BuildConfig
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Stage 0/1: unit-test builds must never enable automatic AI SOS.
 * Release Gradle config hard-codes false; this catches accidental defaultConfig flips.
 */
class AiFeatureFlagsTest {

    @Test
    fun aiAutoSos_buildConfig_isDisabled() {
        assertFalse(
            "BuildConfig.AI_AUTO_SOS_ENABLED must be false until Stage 2+ sign-off",
            BuildConfig.AI_AUTO_SOS_ENABLED,
        )
    }

    @Test
    fun aiAutoSos_featureFlag_mirrorsBuildConfig() {
        assertFalse(AiFeatureFlags.AI_AUTO_SOS_ENABLED)
    }

    @Test
    fun demoMode_buildConfig_isEnabled() {
        assertTrue(
            "BuildConfig.DEMO_MODE must remain true for Internal Testing",
            BuildConfig.DEMO_MODE,
        )
    }
}
