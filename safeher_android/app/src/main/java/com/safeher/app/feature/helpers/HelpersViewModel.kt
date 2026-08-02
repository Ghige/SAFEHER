package com.safeher.app.feature.helpers

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.session.AlertSessionManager
import com.safeher.app.domain.model.NearbyHelper
import com.safeher.app.domain.repository.HelpersRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class HelpersViewModel @Inject constructor(
    private val helpersRepository: HelpersRepository,
    private val alertSessionManager: AlertSessionManager,
    private val networkMonitor: NetworkMonitor,
) : ViewModel() {

    private val _uiState = MutableStateFlow(HelpersUiState())
    val uiState: StateFlow<HelpersUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<HelpersEvent>()
    val events: SharedFlow<HelpersEvent> = _events.asSharedFlow()

    init {
        observeNetwork()
        observeActiveAlert()
    }

    fun loadHelpers() {
        val alertId = _uiState.value.activeAlertId
        if (alertId == null) {
            _uiState.update { it.copy(isLoading = false, helpers = emptyList(), error = null) }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            fetchHelpers(alertId, isRefresh = false)
        }
    }

    fun refreshHelpers() {
        val alertId = _uiState.value.activeAlertId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isRefreshing = true, error = null) }
            fetchHelpers(alertId, isRefresh = true)
        }
    }

    fun onHelperClick(helper: NearbyHelper) {
        viewModelScope.launch {
            _events.emit(HelpersEvent.NavigateToProfile(helper.id))
        }
    }

    fun onRespondClick(helper: NearbyHelper) {
        _uiState.update { it.copy(helperToRespond = helper) }
    }

    fun onBlockClick(helper: NearbyHelper) {
        _uiState.update { it.copy(helperToBlock = helper) }
    }

    fun dismissRespondDialog() {
        _uiState.update { it.copy(helperToRespond = null) }
    }

    fun dismissBlockDialog() {
        _uiState.update { it.copy(helperToBlock = null) }
    }

    fun confirmRespond(action: HelperResponseAction) {
        val helper = _uiState.value.helperToRespond ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isResponding = true) }
            when (action) {
                HelperResponseAction.ACCEPT -> {
                    val result = helpersRepository.respondToAlert(helper.alertId)
                    _uiState.update { it.copy(isResponding = false, helperToRespond = null) }
                    result.fold(
                        onSuccess = { updated ->
                            updateHelperInList(updated)
                            _uiState.update {
                                it.copy(snackbarMessage = "Response sent successfully")
                            }
                        },
                        onFailure = { error ->
                            _uiState.update { it.copy(error = error.message) }
                        },
                    )
                }
                HelperResponseAction.DECLINE -> {
                    blockHelperInternal(helper)
                    _uiState.update { it.copy(isResponding = false, helperToRespond = null) }
                }
            }
        }
    }

    fun confirmBlock() {
        val helper = _uiState.value.helperToBlock ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isBlocking = true) }
            blockHelperInternal(helper)
            _uiState.update { it.copy(isBlocking = false, helperToBlock = null) }
        }
    }

    fun navigateToBlocked() {
        viewModelScope.launch { _events.emit(HelpersEvent.NavigateToBlocked) }
    }

    fun clearSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    private suspend fun fetchHelpers(alertId: String, isRefresh: Boolean) {
        val result = helpersRepository.getNearbyHelpers(alertId)
        result.fold(
            onSuccess = { helpers ->
                val active = helpers.filterNot { it.isBlocked }
                val blocked = helpers.filter { it.isBlocked }
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isRefreshing = false,
                        helpers = active,
                        blockedHelpers = blocked,
                        error = null,
                    )
                }
            },
            onFailure = { error ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = error.message,
                    )
                }
            },
        )
    }

    private suspend fun blockHelperInternal(helper: NearbyHelper) {
        val result = helpersRepository.blockHelper(helper.id)
        result.fold(
            onSuccess = {
                val blocked = helper.copy(status = "cancelled")
                _uiState.update { state ->
                    state.copy(
                        helpers = state.helpers.filterNot { it.id == helper.id },
                        blockedHelpers = state.blockedHelpers + blocked,
                        snackbarMessage = "Helper blocked",
                    )
                }
            },
            onFailure = { error ->
                _uiState.update { it.copy(error = error.message) }
            },
        )
    }

    private fun updateHelperInList(updated: NearbyHelper) {
        _uiState.update { state ->
            state.copy(
                helpers = state.helpers.map { if (it.id == updated.id) updated else it },
            )
        }
    }

    private fun observeNetwork() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { online ->
                _uiState.update { it.copy(isOffline = !online) }
            }
        }
    }

    private fun observeActiveAlert() {
        viewModelScope.launch {
            alertSessionManager.activeAlert.collect { alert ->
                val alertId = alert?.takeIf { it.isOngoing }?.id
                _uiState.update { it.copy(activeAlertId = alertId) }
                if (alertId != null) {
                    loadHelpers()
                } else {
                    _uiState.update {
                        it.copy(isLoading = false, helpers = emptyList(), blockedHelpers = emptyList())
                    }
                }
            }
        }
    }
}
