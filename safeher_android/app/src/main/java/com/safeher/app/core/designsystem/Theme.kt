package com.safeher.app.core.designsystem

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = SafeHerPrimary,
    onPrimary = SafeHerOnPrimary,
    primaryContainer = SafeHerLightPink,
    onPrimaryContainer = SafeHerTextPrimary,
    secondary = SafeHerSecondaryPink,
    onSecondary = SafeHerTextPrimary,
    secondaryContainer = SafeHerLightPink,
    onSecondaryContainer = SafeHerTextPrimary,
    tertiary = SafeHerSecondaryPink,
    onTertiary = SafeHerTextPrimary,
    background = SafeHerBackground,
    onBackground = SafeHerTextPrimary,
    surface = SafeHerSurface,
    onSurface = SafeHerTextPrimary,
    surfaceVariant = SafeHerLightPink,
    onSurfaceVariant = SafeHerTextSecondary,
    outline = SafeHerBorder,
    outlineVariant = SafeHerBorder,
    error = SafeHerDanger,
    onError = SafeHerOnPrimary,
    errorContainer = SafeHerDangerLight,
    onErrorContainer = SafeHerDanger,
)

@Composable
fun SafeHerTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    // SafeHer redesign is light-first; keep light palette even if system dark is on.
    val colorScheme = LightColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            window.navigationBarColor = Color.White.toArgb()
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = true
                isAppearanceLightNavigationBars = true
            }
        }
    }
    MaterialTheme(
        colorScheme = colorScheme,
        typography = SafeHerTypography,
        shapes = SafeHerShapes,
        content = content,
    )
}
