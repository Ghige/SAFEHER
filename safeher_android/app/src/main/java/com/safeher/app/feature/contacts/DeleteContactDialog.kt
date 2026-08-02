package com.safeher.app.feature.contacts

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.safeher.app.R
import com.safeher.app.domain.model.EmergencyContact

@Composable
fun DeleteContactDialog(
    contact: EmergencyContact,
    isDeleting: Boolean,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { if (!isDeleting) onDismiss() },
        title = {
            Text(text = stringResource(R.string.contacts_delete_title))
        },
        text = {
            Text(text = stringResource(R.string.contacts_delete_message))
        },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                enabled = !isDeleting,
            ) {
                Text(
                    text = stringResource(R.string.contacts_delete_confirm),
                    color = MaterialTheme.colorScheme.error,
                )
            }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                enabled = !isDeleting,
            ) {
                Text(stringResource(R.string.contacts_delete_cancel))
            }
        },
    )
}
