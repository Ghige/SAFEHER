package com.safeher.app.core.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.compose.rememberNavController
import com.safeher.app.R
import com.safeher.app.core.ui.navigation.SafeHerNavGraph
import com.safeher.app.core.session.SessionCleanupManager
import com.safeher.app.domain.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@Composable
fun SafeHerAppRoot() {
    val navController = rememberNavController()
    SafeHerNavGraph(navController = navController)
}

@Composable
fun PlaceholderScreen(
    onLogout: () -> Unit = {},
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = stringResource(R.string.placeholder_title),
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(16.dp))
            TextButton(onClick = onLogout) {
                Text(stringResource(R.string.logout))
            }
        }
    }
}

@HiltViewModel
class RootViewModel @Inject constructor(
    val authRepository: AuthRepository,
    private val sessionCleanupManager: SessionCleanupManager,
) : ViewModel() {

    fun logout(onComplete: () -> Unit) {
        viewModelScope.launch {
            sessionCleanupManager.performLogout()
            onComplete()
        }
    }
}
