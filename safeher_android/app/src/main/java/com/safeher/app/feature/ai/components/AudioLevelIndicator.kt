package com.safeher.app.feature.ai.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.unit.dp

@Composable
fun AudioLevelIndicator(
    level: Float,
    isActive: Boolean,
    modifier: Modifier = Modifier,
) {
    val alpha = if (isActive) 0.3f + (level * 0.7f) else 0.2f
    Box(
        modifier = modifier
            .size(64.dp)
            .background(
                MaterialTheme.colorScheme.primary.copy(alpha = alpha),
                CircleShape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Default.Mic,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onPrimary,
            modifier = Modifier
                .size(32.dp)
                .alpha(if (isActive) 1f else 0.5f),
        )
    }
}

@Composable
fun ListeningAnimation(
    isListening: Boolean,
    modifier: Modifier = Modifier,
) {
    if (!isListening) return
    val transition = rememberInfiniteTransition(label = "listening")
    val scale by transition.animateFloat(
        initialValue = 1f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(800),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse",
    )
    Box(
        modifier = modifier
            .size(80.dp)
            .scale(scale)
            .background(
                MaterialTheme.colorScheme.error.copy(alpha = 0.15f),
                CircleShape,
            ),
    )
}
