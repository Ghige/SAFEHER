package com.safeher.app.feature.helpers

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.ui.navigation.Route
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.NearbyHelper
import com.safeher.app.domain.repository.HelpersRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HelperProfileUiState(
    val isLoading: Boolean = true,
    val helper: NearbyHelper? = null,
    val error: String? = null,
    val isOffline: Boolean = false,
    val isBlocking: Boolean = false,
    val isResponding: Boolean = false,
    val showResponseDialog: Boolean = false,
    val snackbarMessage: String? = null,
)

@HiltViewModel
class HelperProfileViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val helpersRepository: HelpersRepository,
    private val alertSessionManager: AlertSessionManager,
    private val networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val helperId: String = savedStateHandle.get<String>(Route.HELPER_ID_ARG).orEmpty()

    private val _uiState = MutableStateFlow(HelperProfileUiState())
    val uiState: StateFlow<HelperProfileUiState> = _uiState.asStateFlow()

    init {
        observeNetwork()
        loadHelper()
    }

    fun loadHelper() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val alertId = alertSessionManager.activeAlert.value?.takeIf { it.isOngoing }?.id
            if (alertId == null) {
                _uiState.update { it.copy(isLoading = false, error = "No active alert found") }
                return@launch
            }
            val result = helpersRepository.getNearbyHelpers(alertId)
            result.fold(
                onSuccess = { helpers ->
                    val helper = helpers.find { it.id == helperId }
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            helper = helper,
                            error = if (helper == null) "Helper not found" else null,
                        )
                    }
                },
                onFailure = { error ->
                    _uiState.update { it.copy(isLoading = false, error = error.message) }
                },
            )
        }
    }

    fun showResponseDialog() {
        _uiState.update { it.copy(showResponseDialog = true) }
    }

    fun dismissResponseDialog() {
        _uiState.update { it.copy(showResponseDialog = false) }
    }

    fun confirmRespond(action: HelperResponseAction) {
        val helper = _uiState.value.helper ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isResponding = true, showResponseDialog = false) }
            when (action) {
                HelperResponseAction.ACCEPT -> {
                    val result = helpersRepository.respondToAlert(helper.alertId)
                    _uiState.update { it.copy(isResponding = false) }
                    result.fold(
                        onSuccess = { updated ->
                            _uiState.update {
                                it.copy(helper = updated, snackbarMessage = "Response sent")
                            }
                        },
                        onFailure = { error ->
                            _uiState.update { it.copy(error = error.message) }
                        },
                    )
                }
                HelperResponseAction.DECLINE -> {
                    blockHelper(helper)
                    _uiState.update { it.copy(isResponding = false) }
                }
            }
        }
    }

    fun blockHelper() {
        val helper = _uiState.value.helper ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isBlocking = true) }
            blockHelper(helper)
            _uiState.update { it.copy(isBlocking = false) }
        }
    }

    fun clearSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    private suspend fun blockHelper(helper: NearbyHelper) {
        val result = helpersRepository.blockHelper(helper.id)
        result.fold(
            onSuccess = {
                _uiState.update {
                    it.copy(
                        helper = helper.copy(status = "cancelled"),
                        snackbarMessage = "Helper blocked",
                    )
                }
            },
            onFailure = { error ->
                _uiState.update { it.copy(error = error.message) }
            },
        )
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }
}
