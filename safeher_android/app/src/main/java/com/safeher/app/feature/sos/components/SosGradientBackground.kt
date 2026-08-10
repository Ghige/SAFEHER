package com.safeher.app.feature.sos.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.material3.MaterialTheme

@Composable
fun SosGradientBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val errorTint = MaterialTheme.colorScheme.error
    val surface = MaterialTheme.colorScheme.surface
    val primaryTint = MaterialTheme.colorScheme.primary

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                brush = Brush.linearGradient(
                    colors = listOf(
                        errorTint.copy(alpha = 0.08f),
                        surface,
                        primaryTint.copy(alpha = 0.06f),
                    ),
                    start = Offset(0f, 0f),
                    end = Offset(Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY),
                ),
            ),
    ) {
        content()
    }
}
