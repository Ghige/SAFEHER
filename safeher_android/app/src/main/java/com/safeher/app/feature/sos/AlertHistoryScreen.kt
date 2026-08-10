package com.safeher.app.feature.sos

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safeher.app.R
import com.safeher.app.core.designsystem.SafeHerPrimary
import com.safeher.app.core.designsystem.SafeHerTextSecondary
import com.safeher.app.feature.home.components.ErrorType
import com.safeher.app.feature.home.components.ErrorView
import com.safeher.app.feature.home.components.OfflineBanner
import com.safeher.app.feature.home.components.SafeHerScreenHeader
import com.safeher.app.feature.sos.components.AlertHistoryCard
import com.safeher.app.feature.sos.components.LoadingSOS

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlertHistoryScreen(
    contentPadding: PaddingValues = PaddingValues(),
    viewModel: AlertHistoryViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(padding),
        ) {
            SafeHerScreenHeader(title = stringResource(R.string.nav_history))

            if (uiState.isOffline) {
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    OfflineBanner()
                }
            }

            HistoryFilterRow(
                selected = uiState.selectedFilter,
                onFilterSelected = viewModel::setFilter,
            )

            when {
                uiState.isLoading && uiState.history.isEmpty() -> LoadingSOS()
                uiState.error != null && uiState.history.isEmpty() -> {
                    ErrorView(
                        message = uiState.error.orEmpty(),
                        onRetry = viewModel::loadHistory,
                        errorType = if (uiState.isOffline) ErrorType.OFFLINE else ErrorType.NETWORK,
                    )
                }
                uiState.filteredHistory.isEmpty() -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text(
                            text = stringResource(R.string.sos_history_empty_title),
                            style = MaterialTheme.typography.titleMedium,
                            color = SafeHerTextSecondary,
                        )
                        Text(
                            text = stringResource(R.string.sos_history_empty_message),
                            style = MaterialTheme.typography.bodyMedium,
                            color = SafeHerTextSecondary,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                }
                else -> {
                    PullToRefreshBox(
                        isRefreshing = uiState.isLoading,
                        onRefresh = viewModel::loadHistory,
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            items(uiState.filteredHistory, key = { it.id }) { alert ->
                                AlertHistoryCard(alert = alert)
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HistoryFilterRow(
    selected: AlertHistoryFilter,
    onFilterSelected: (AlertHistoryFilter) -> Unit,
) {
    val filters = listOf(
        AlertHistoryFilter.ALL to R.string.history_filter_all,
        AlertHistoryFilter.SOS to R.string.history_filter_sos,
        AlertHistoryFilter.AI to R.string.history_filter_ai,
        AlertHistoryFilter.LOCATION to R.string.history_filter_location,
    )
    androidx.compose.foundation.layout.Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        filters.forEach { (filter, labelRes) ->
            FilterChip(
                selected = selected == filter,
                onClick = { onFilterSelected(filter) },
                label = { Text(stringResource(labelRes)) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = com.safeher.app.core.designsystem.SafeHerLightPink,
                    selectedLabelColor = SafeHerPrimary,
                ),
            )
        }
    }
}
