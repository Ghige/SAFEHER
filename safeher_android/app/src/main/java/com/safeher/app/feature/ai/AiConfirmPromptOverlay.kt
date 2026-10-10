package com.safeher.app.feature.ai

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.feature.ai.components.AiEmergencyConfirmationCard
import kotlinx.coroutines.flow.collectLatest

@Composable
fun AiConfirmPromptHost(
    viewModel: AiConfirmPromptViewModel,
    onNavigateToSosCountdown: () -> Unit,
    dialogEnabled: Boolean = true,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(viewModel) {
        viewModel.events.collectLatest { event ->
            if (event == AiConfirmPromptEvent.NavigateToSosCountdown) {
                onNavigateToSosCountdown()
            }
        }
    }

    if (!dialogEnabled) return
    if (!uiState.visible || uiState.step == AiConfirmPromptStep.HIDDEN) return

    Dialog(
        onDismissRequest = { },
        properties = DialogProperties(
            dismissOnBackPress = false,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
        ),
    ) {
        val isSendAlert = uiState.step == AiConfirmPromptStep.SEND_ALERT
        AiEmergencyConfirmationCard(
            onConfirmSafe = {
                if (isSendAlert) viewModel.onCancelSendAlert() else viewModel.onImOkay()
            },
            onConfirmSos = {
                if (isSendAlert) viewModel.onSendEmergencyAlert() else viewModel.onNeedHelp()
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp),
            title = stringResource(
                if (isSendAlert) R.string.ai_confirm_send_title else R.string.ai_confirm_help_title,
            ),
            body = stringResource(
                if (isSendAlert) R.string.ai_confirm_send_body else R.string.ai_confirm_help_body,
            ),
            confirmLabel = stringResource(
                if (isSendAlert) R.string.ai_confirm_send_yes else R.string.ai_confirm_help_yes,
            ),
            dismissLabel = stringResource(
                if (isSendAlert) R.string.ai_confirm_send_no else R.string.ai_confirm_help_no,
            ),
            secondsRemaining = if (isSendAlert) null else uiState.secondsRemaining,
        )
    }
}
