package com.safeher.app.feature.sos.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.safeher.app.core.designsystem.SafeHerDanger
import com.safeher.app.core.designsystem.SafeHerLightPink
import com.safeher.app.core.designsystem.SafeHerOnPrimary
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerSecondaryPink

@Composable
fun SOSButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    subtitle: String = "Tap or hold to\nsend alert",
    holdHint: String = "Hold for 3 seconds",
) {
    val infiniteTransition = rememberInfiniteTransition(label = "sos_pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.04f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "sos_scale",
    )

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(contentAlignment = Alignment.Center) {
            listOf(200.dp, 170.dp, 140.dp).forEachIndexed { index, ringSize ->
                Box(
                    modifier = Modifier
                        .size(ringSize)
                        .scale(if (enabled && index == 0) scale else 1f)
                        .clip(CircleShape)
                        .background(
                            when (index) {
                                0 -> SafeHerLightPink.copy(alpha = 0.45f)
                                1 -> SafeHerSecondaryPink.copy(alpha = 0.35f)
                                else -> SafeHerSecondaryPink.copy(alpha = 0.2f)
                            },
                        ),
                )
            }

            Box(
                modifier = Modifier
                    .size(120.dp)
                    .clip(CircleShape)
                    .background(SafeHerPrimary)
                    .pointerInput(enabled, onClick) {
                        if (enabled) {
                            detectTapGestures(onTap = { onClick() })
                        }
                    },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "SOS",
                    color = SafeHerOnPrimary,
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Text(
            text = subtitle,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .then(Modifier),
        )
        Text(
            text = holdHint,
            style = MaterialTheme.typography.labelSmall,
            color = SafeHerDanger,
            modifier = Modifier.align(Alignment.CenterHorizontally),
        )
    }
}

@Composable
fun HomeSosSection(
    onSosClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        SOSButton(
            onClick = onSosClick,
            enabled = enabled,
        )
    }
}
