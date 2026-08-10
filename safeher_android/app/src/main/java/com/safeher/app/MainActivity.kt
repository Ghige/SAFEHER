package com.safeher.app

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.core.datastore.SettingsStore
import com.safeher.app.core.designsystem.SafeHerTheme
import com.safeher.app.core.ui.SafeHerAppRoot
import com.safeher.app.domain.model.AppThemeMode
import com.safeher.app.services.AppForegroundTracker
import dagger.hilt.android.AndroidEntryPoint
import timber.log.Timber
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var settingsStore: SettingsStore
    @Inject lateinit var appForegroundTracker: AppForegroundTracker

    override fun onCreate(savedInstanceState: Bundle?) {
        Timber.d("MainActivity.onCreate savedInstanceState=%s", savedInstanceState != null)
        super.onCreate(savedInstanceState)
        appForegroundTracker.register()
        // Edge-to-edge breaks frame presentation on API 36+ preview emulators.
        WindowCompat.setDecorFitsSystemWindows(window, true)
        setContent {
            Timber.d("MainActivity.setContent composing")
            val themeMode by settingsStore.themeMode.collectAsStateWithLifecycle(
                initialValue = AppThemeMode.SYSTEM,
            )
            val darkTheme = when (themeMode) {
                AppThemeMode.DARK -> true
                AppThemeMode.LIGHT -> false
                AppThemeMode.SYSTEM -> isSystemInDarkTheme()
            }
            SafeHerTheme(darkTheme = darkTheme) {
                SafeHerAppRoot()
            }
        }
    }

    override fun onStart() {
        super.onStart()
        Timber.d("MainActivity.onStart")
    }

    override fun onResume() {
        super.onResume()
        Timber.d("MainActivity.onResume")
    }

    override fun onPause() {
        Timber.d("MainActivity.onPause")
        super.onPause()
    }

    override fun onDestroy() {
        Timber.d("MainActivity.onDestroy isFinishing=%s", isFinishing)
        super.onDestroy()
    }
}
