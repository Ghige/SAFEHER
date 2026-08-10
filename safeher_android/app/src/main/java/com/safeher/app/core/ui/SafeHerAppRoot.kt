package com.safeher.app.core.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.compose.rememberNavController
import com.safeher.app.core.ui.navigation.SafeHerNavGraph
import com.safeher.app.core.session.SessionCleanupManager
import com.safeher.app.domain.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@Composable
fun SafeHerAppRoot() {
    LaunchedEffect(Unit) {
        Timber.d("SafeHerAppRoot: first composition")
    }
    val navController = rememberNavController()
    Surface(
        modifier = androidx.compose.ui.Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        SafeHerNavGraph(navController = navController)
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
