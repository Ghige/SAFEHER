package com.safeher.app.feature.helpers

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.safeher.app.R

@Composable
fun HelperResponseDialog(
    onAccept: () -> Unit,
    onDecline: () -> Unit,
    onDismiss: () -> Unit,
    isLoading: Boolean = false,
) {
    AlertDialog(
        onDismissRequest = { if (!isLoading) onDismiss() },
        title = { Text(stringResource(R.string.helpers_response_title)) },
        text = { Text(stringResource(R.string.helpers_response_message)) },
        confirmButton = {
            TextButton(onClick = onAccept, enabled = !isLoading) {
                Text(stringResource(R.string.helpers_accept))
            }
        },
        dismissButton = {
            TextButton(onClick = onDecline, enabled = !isLoading) {
                Text(stringResource(R.string.helpers_decline))
            }
        },
    )
}

@Composable
fun HelperBlockDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    isLoading: Boolean = false,
) {
    AlertDialog(
        onDismissRequest = { if (!isLoading) onDismiss() },
        title = { Text(stringResource(R.string.helpers_block_title)) },
        text = { Text(stringResource(R.string.helpers_block_message)) },
        confirmButton = {
            TextButton(onClick = onConfirm, enabled = !isLoading) {
                Text(stringResource(R.string.helpers_block_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isLoading) {
                Text(stringResource(R.string.contacts_delete_cancel))
            }
        },
    )
}
