package com.safeher.app.feature.sos

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.safeher.app.R

@Composable
fun CancelSOSDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    isLoading: Boolean = false,
) {
    AlertDialog(
        onDismissRequest = { if (!isLoading) onDismiss() },
        title = { Text(stringResource(R.string.sos_cancel_title)) },
        text = { Text(stringResource(R.string.sos_cancel_message)) },
        confirmButton = {
            TextButton(onClick = onConfirm, enabled = !isLoading) {
                Text(stringResource(R.string.sos_cancel_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isLoading) {
                Text(stringResource(R.string.contacts_delete_cancel))
            }
        },
    )
}
