package com.safeher.app.core.designsystem

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = SafeHerPrimary,
    onPrimary = SafeHerOnPrimary,
    secondary = SafeHerSecondary,
    background = SafeHerBackground,
    surface = SafeHerSurface,
    error = SafeHerError,
)

private val DarkColorScheme = darkColorScheme(
    primary = SafeHerPrimary,
    onPrimary = SafeHerOnPrimary,
    secondary = SafeHerSecondary,
    error = SafeHerError,
)

@Composable
fun SafeHerTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
        typography = SafeHerTypography,
        shapes = SafeHerShapes,
        content = content,
    )
}
