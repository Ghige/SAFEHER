package com.safeher.app.core.designsystem.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.safeher.app.core.designsystem.SafeHerBorder
import com.safeher.app.core.designsystem.SafeHerCard
import com.safeher.app.core.designsystem.SafeHerCardShape
import com.safeher.app.core.designsystem.SafeHerSpacing

@Composable
fun SafeHerCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    border: Boolean = true,
    elevation: Dp = SafeHerSpacing.cardElevation,
    content: @Composable ColumnScope.() -> Unit,
) {
    val cardModifier = modifier
    if (onClick != null) {
        Card(
            onClick = onClick,
            modifier = cardModifier,
            shape = SafeHerCardShape,
            colors = CardDefaults.cardColors(containerColor = SafeHerCard),
            elevation = CardDefaults.cardElevation(defaultElevation = elevation),
            border = if (border) BorderStroke(1.dp, SafeHerBorder) else null,
        ) {
            Column(modifier = Modifier.padding(SafeHerSpacing.cardPadding), content = content)
        }
    } else {
        Card(
            modifier = cardModifier,
            shape = SafeHerCardShape,
            colors = CardDefaults.cardColors(containerColor = SafeHerCard),
            elevation = CardDefaults.cardElevation(defaultElevation = elevation),
            border = if (border) BorderStroke(1.dp, SafeHerBorder) else null,
        ) {
            Column(modifier = Modifier.padding(SafeHerSpacing.cardPadding), content = content)
        }
    }
}

@Composable
fun SafeHerStatusBadge(
    text: String,
    isActive: Boolean,
    modifier: Modifier = Modifier,
) {
    androidx.compose.material3.Surface(
        modifier = modifier,
        shape = MaterialTheme.shapes.small,
        color = if (isActive) {
            com.safeher.app.core.designsystem.SafeHerLightPink
        } else {
            MaterialTheme.colorScheme.surfaceVariant
        },
    ) {
        androidx.compose.material3.Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            color = if (isActive) {
                com.safeher.app.core.designsystem.SafeHerPrimary
            } else {
                com.safeher.app.core.designsystem.SafeHerTextSecondary
            },
        )
    }
}
