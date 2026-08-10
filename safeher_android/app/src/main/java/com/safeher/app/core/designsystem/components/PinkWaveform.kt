package com.safeher.app.core.designsystem.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerSecondaryPink
import kotlin.math.sin

@Composable
fun PinkWaveform(
    modifier: Modifier = Modifier,
    isActive: Boolean = true,
    barCount: Int = 24,
    height: androidx.compose.ui.unit.Dp = 48.dp,
    primaryColor: Color = SafeHerPrimary,
    secondaryColor: Color = SafeHerSecondaryPink,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "waveform")
    val phase by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 6.28f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "wave_phase",
    )

    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .height(height),
    ) {
        if (!isActive) {
            val barWidth = size.width / (barCount * 2f)
            repeat(barCount) { index ->
                val x = index * barWidth * 2 + barWidth / 2
                drawRoundRect(
                    color = secondaryColor.copy(alpha = 0.5f),
                    topLeft = Offset(x, size.height * 0.35f),
                    size = Size(barWidth, size.height * 0.3f),
                    cornerRadius = CornerRadius(barWidth / 2, barWidth / 2),
                )
            }
            return@Canvas
        }

        val barWidth = size.width / (barCount * 2f)
        repeat(barCount) { index ->
            val normalized = index.toFloat() / barCount
            val wave = sin(normalized * 8 + phase).toFloat()
            val barHeight = (0.25f + (wave + 1f) * 0.25f) * size.height
            val x = index * barWidth * 2 + barWidth / 2
            val y = (size.height - barHeight) / 2f
            drawRoundRect(
                color = if (index % 3 == 0) primaryColor else secondaryColor,
                topLeft = Offset(x, y),
                size = Size(barWidth, barHeight),
                cornerRadius = CornerRadius(barWidth / 2, barWidth / 2),
            )
        }
    }
}
