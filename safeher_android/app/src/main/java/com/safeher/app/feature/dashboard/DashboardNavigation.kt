package com.safeher.app.feature.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.safeher.app.R
import com.safeher.app.core.ui.navigation.Route
import com.safeher.app.feature.contacts.AddContactScreen
import com.safeher.app.feature.contacts.ContactsScreen
import com.safeher.app.feature.home.components.HomeBottomNavigation
import com.safeher.app.feature.home.components.HomeTopBar
import com.safeher.app.feature.profile.ProfileScreen
import com.safeher.app.feature.sos.ActiveAlertScreen
import com.safeher.app.feature.sos.AlertHistoryScreen
import com.safeher.app.feature.sos.CountdownScreen
import com.safeher.app.feature.sos.SOSEvent
import com.safeher.app.feature.sos.SOSScreen
import com.safeher.app.feature.ai.AiConfirmPromptHost
import com.safeher.app.feature.ai.AiConfirmPromptViewModel
import com.safeher.app.feature.ai.AiMonitoringScreen
import com.safeher.app.feature.ai.AiMonitoringViewModel
import com.safeher.app.feature.ai.AiSettingsScreen
import com.safeher.app.feature.ai.AiStatusScreen
import com.safeher.app.feature.helpers.BlockedHelpersScreen
import com.safeher.app.feature.helpers.HelperProfileScreen
import com.safeher.app.feature.helpers.HelpersScreen
import com.safeher.app.feature.helpers.HelpersViewModel
import com.safeher.app.feature.location.LocationPermissionScreen
import com.safeher.app.feature.location.LocationScreen
import com.safeher.app.feature.location.TrackLocationScreen
import com.safeher.app.feature.settings.AboutScreen
import com.safeher.app.feature.settings.BatteryOptimizationScreen
import com.safeher.app.feature.settings.NotificationSettingsScreen
import com.safeher.app.feature.settings.PermissionScreen
import com.safeher.app.feature.settings.PrivacyPolicyScreen
import com.safeher.app.feature.settings.SecurityScreen
import com.safeher.app.feature.settings.SettingsEvent
import com.safeher.app.feature.settings.SettingsScreen
import com.safeher.app.feature.settings.TermsScreen
import com.safeher.app.feature.sos.rememberSosViewModel
import kotlinx.coroutines.flow.collectLatest
import timber.log.Timber

object DashboardRoutes {
    const val DASHBOARD = "dashboard"
    const val PROFILE = "profile"
}

@Composable
fun DashboardNavigation(
    onLogout: () -> Unit,
) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    val sosViewModel = rememberSosViewModel()
    val confirmViewModel: AiConfirmPromptViewModel = hiltViewModel()

    LaunchedEffect(currentRoute) {
        Timber.d("DashboardNavigation: currentRoute=%s", currentRoute)
    }

    LaunchedEffect(Unit) {
        Timber.d("DashboardNavigation: syncActiveAlertUi")
        sosViewModel.syncActiveAlertUi()
    }

    LaunchedEffect(Unit) {
        sosViewModel.events.collectLatest { event ->
            when (event) {
                SOSEvent.NavigateToActive -> {
                    val route = navController.currentBackStackEntry?.destination?.route
                    if (route != Route.SOS_ACTIVE) {
                        Timber.d("DashboardNavigation: navigate to SOS_ACTIVE from %s", route)
                        navController.navigate(Route.SOS_ACTIVE) {
                            popUpTo(Route.SOS_COUNTDOWN) { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                }
                SOSEvent.NavigateToCountdown -> {
                    navController.navigate(Route.SOS_COUNTDOWN) {
                        launchSingleTop = true
                    }
                }
                else -> Unit
            }
        }
    }

    val showBottomBar = currentRoute == DashboardRoutes.DASHBOARD ||
        currentRoute == DashboardRoutes.PROFILE ||
        currentRoute == Route.SOS ||
        currentRoute == Route.SOS_HISTORY ||
        currentRoute == Route.AI

    val screensWithOwnHeader = setOf(
        DashboardRoutes.DASHBOARD,
        DashboardRoutes.PROFILE,
        Route.SOS,
        Route.SOS_HISTORY,
        Route.AI,
        Route.LOCATION,
    )

    val showBack = currentRoute?.startsWith("coming_soon") == true ||
        currentRoute == Route.CONTACTS ||
        currentRoute == Route.ADD_CONTACT ||
        (currentRoute?.startsWith("sos") == true && currentRoute !in screensWithOwnHeader) ||
        (currentRoute?.startsWith("location") == true && currentRoute != Route.LOCATION) ||
        currentRoute?.startsWith("helpers") == true ||
        (currentRoute?.startsWith("ai") == true && currentRoute != Route.AI) ||
        currentRoute?.startsWith("settings") == true

    val showTopBar = !screensWithOwnHeader.contains(currentRoute) && showBack

    val topBarTitle = when (currentRoute) {
        DashboardRoutes.PROFILE -> stringResource(R.string.nav_profile)
        Route.CONTACTS -> stringResource(R.string.action_contacts)
        Route.ADD_CONTACT -> stringResource(R.string.contacts_add_title)
        Route.SOS, Route.SOS_COUNTDOWN -> stringResource(R.string.action_sos)
        Route.SOS_ACTIVE -> stringResource(R.string.sos_active_title)
        Route.SOS_HISTORY -> stringResource(R.string.sos_view_history)
        Route.LOCATION -> stringResource(R.string.action_live_location)
        Route.LOCATION_PERMISSION -> stringResource(R.string.location_permission_title)
        Route.LOCATION_TRACK -> stringResource(R.string.location_track_title)
        Route.HELPERS -> stringResource(R.string.action_helpers)
        Route.HELPER_PROFILE -> stringResource(R.string.helpers_profile_title)
        Route.HELPERS_BLOCKED -> stringResource(R.string.helpers_blocked_title)
        Route.AI -> stringResource(R.string.action_ai)
        Route.AI_STATUS -> stringResource(R.string.ai_status_title)
        Route.AI_SETTINGS -> stringResource(R.string.ai_settings_title)
        Route.SETTINGS -> stringResource(R.string.action_settings)
        Route.SETTINGS_PERMISSIONS -> stringResource(R.string.settings_permissions)
        Route.SETTINGS_NOTIFICATIONS -> stringResource(R.string.settings_notifications_manage)
        Route.SETTINGS_SECURITY -> stringResource(R.string.settings_security)
        Route.SETTINGS_ABOUT -> stringResource(R.string.settings_about)
        Route.SETTINGS_PRIVACY -> stringResource(R.string.settings_privacy_policy)
        Route.SETTINGS_TERMS -> stringResource(R.string.settings_terms)
        Route.SETTINGS_BATTERY -> stringResource(R.string.settings_battery)
        Route.COMING_SOON -> stringResource(R.string.coming_soon_title)
        else -> stringResource(R.string.app_name)
    }

    Box(modifier = Modifier.fillMaxSize()) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
        topBar = {
            HomeTopBar(
                title = topBarTitle,
                showBack = showBack,
                onBack = { navController.popBackStack() },
            )
        },
        bottomBar = {
            if (showBottomBar) {
                HomeBottomNavigation(
                    currentRoute = currentRoute,
                    onNavigate = { route ->
                        navController.navigate(route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                )
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = DashboardRoutes.DASHBOARD,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            composable(DashboardRoutes.DASHBOARD) {
                DashboardScreen(
                    onNavigateToComingSoon = { feature ->
                        when (feature) {
                            QuickActionFeature.CONTACTS.routeKey ->
                                navController.navigate(Route.CONTACTS)
                            QuickActionFeature.SOS.routeKey ->
                                navController.navigate(Route.SOS)
                            QuickActionFeature.LIVE_LOCATION.routeKey ->
                                navController.navigate(Route.LOCATION)
                            QuickActionFeature.HELPERS.routeKey ->
                                navController.navigate(Route.HELPERS)
                            QuickActionFeature.AI.routeKey ->
                                navController.navigate(Route.AI)
                            QuickActionFeature.HISTORY.routeKey ->
                                navController.navigate(Route.SOS_HISTORY)
                            QuickActionFeature.SETTINGS.routeKey ->
                                navController.navigate(Route.SETTINGS)
                            else ->
                                navController.navigate(Route.comingSoon(feature))
                        }
                    },
                    onSosClick = {
                        sosViewModel.onSosButtonClick()
                    },
                    onNavigateToSettings = { navController.navigate(Route.SETTINGS) },
                )
            }

            composable(DashboardRoutes.PROFILE) {
                ProfileScreen(
                    onNavigateToLogin = onLogout,
                    onNavigateToSettings = { navController.navigate(Route.SETTINGS) },
                    onNavigateToContacts = { navController.navigate(Route.CONTACTS) },
                    onNavigateToAbout = { navController.navigate(Route.SETTINGS_ABOUT) },
                    onNavigateToSecurity = { navController.navigate(Route.SETTINGS_SECURITY) },
                )
            }

            composable(
                route = Route.COMING_SOON,
                arguments = listOf(
                    navArgument(Route.FEATURE_ARG) { type = NavType.StringType },
                ),
            ) { entry ->
                val feature = entry.arguments?.getString(Route.FEATURE_ARG).orEmpty()
                ComingSoonScreen(featureKey = feature)
            }

            composable(Route.CONTACTS) { entry ->
                ContactsScreen(
                    onNavigateToAddContact = { navController.navigate(Route.ADD_CONTACT) },
                    backStackEntry = entry,
                )
            }

            composable(Route.ADD_CONTACT) {
                AddContactScreen(
                    onNavigateBack = {
                        navController.previousBackStackEntry
                            ?.savedStateHandle
                            ?.set("refresh_contacts", true)
                        navController.popBackStack()
                    },
                )
            }

            composable(Route.SOS) {
                SOSScreen(
                    onNavigateToCountdown = { navController.navigate(Route.SOS_COUNTDOWN) },
                    onNavigateToActive = {
                        navController.navigate(Route.SOS_ACTIVE) {
                            launchSingleTop = true
                        }
                    },
                    onNavigateToHistory = { navController.navigate(Route.SOS_HISTORY) },
                    viewModel = sosViewModel,
                )
            }

            composable(Route.SOS_COUNTDOWN) {
                CountdownScreen(
                    onNavigateBack = { navController.popBackStack() },
                    viewModel = sosViewModel,
                )
            }

            composable(Route.SOS_ACTIVE) {
                ActiveAlertScreen(
                    onNavigateBack = {
                        val returnedHome = navController.popBackStack(
                            DashboardRoutes.DASHBOARD,
                            false,
                        )
                        if (!returnedHome) {
                            navController.navigate(DashboardRoutes.DASHBOARD) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    inclusive = false
                                }
                                launchSingleTop = true
                            }
                        }
                    },
                    viewModel = sosViewModel,
                )
            }

            composable(Route.SOS_HISTORY) {
                AlertHistoryScreen()
            }

            composable(Route.LOCATION) {
                LocationScreen(
                    onNavigateToPermission = { navController.navigate(Route.LOCATION_PERMISSION) },
                    onNavigateToTrack = { navController.navigate(Route.LOCATION_TRACK) },
                )
            }

            composable(Route.LOCATION_PERMISSION) {
                LocationPermissionScreen(
                    onPermissionGranted = { navController.popBackStack() },
                )
            }

            composable(Route.LOCATION_TRACK) {
                TrackLocationScreen()
            }

            composable(Route.HELPERS) { helpersEntry ->
                HelpersScreen(
                    onNavigateToProfile = { helperId ->
                        navController.navigate(Route.helperProfile(helperId))
                    },
                    onNavigateToBlocked = { navController.navigate(Route.HELPERS_BLOCKED) },
                )
            }

            composable(
                route = Route.HELPER_PROFILE,
                arguments = listOf(
                    navArgument(Route.HELPER_ID_ARG) { type = NavType.StringType },
                ),
            ) {
                HelperProfileScreen()
            }

            composable(Route.HELPERS_BLOCKED) { entry ->
                val helpersEntry = remember(entry) {
                    navController.getBackStackEntry(Route.HELPERS)
                }
                BlockedHelpersScreen(
                    viewModel = hiltViewModel<HelpersViewModel>(helpersEntry),
                )
            }

            composable(Route.AI) { aiEntry ->
                AiMonitoringScreen(
                    onNavigateToSosCountdown = {
                        val route = navController.currentBackStackEntry?.destination?.route
                        if (route != Route.SOS_COUNTDOWN) {
                            navController.navigate(Route.SOS_COUNTDOWN) {
                                launchSingleTop = true
                            }
                        }
                    },
                    onNavigateToActiveAlert = {
                        navController.navigate(Route.SOS_ACTIVE) {
                            launchSingleTop = true
                        }
                    },
                    onNavigateToStatus = { navController.navigate(Route.AI_STATUS) },
                    onNavigateToSettings = { navController.navigate(Route.AI_SETTINGS) },
                )
            }

            composable(Route.AI_STATUS) { entry ->
                val aiEntry = remember(entry) {
                    navController.getBackStackEntry(Route.AI)
                }
                AiStatusScreen(viewModel = hiltViewModel<AiMonitoringViewModel>(aiEntry))
            }

            composable(Route.AI_SETTINGS) {
                AiSettingsScreen()
            }

            composable(Route.SETTINGS) {
                SettingsScreen(
                    onNavigate = { event ->
                        handleSettingsNavigation(
                            event = event,
                            navController = navController,
                            onLogout = onLogout,
                        )
                    },
                )
            }

            composable(Route.SETTINGS_PERMISSIONS) {
                PermissionScreen()
            }

            composable(Route.SETTINGS_NOTIFICATIONS) {
                NotificationSettingsScreen()
            }

            composable(Route.SETTINGS_SECURITY) {
                SecurityScreen()
            }

            composable(Route.SETTINGS_ABOUT) {
                AboutScreen(
                    onNavigateToPrivacy = { navController.navigate(Route.SETTINGS_PRIVACY) },
                    onNavigateToTerms = { navController.navigate(Route.SETTINGS_TERMS) },
                )
            }

            composable(Route.SETTINGS_PRIVACY) {
                PrivacyPolicyScreen()
            }

            composable(Route.SETTINGS_TERMS) {
                TermsScreen()
            }

            composable(Route.SETTINGS_BATTERY) {
                BatteryOptimizationScreen()
            }
        }
    }
    AiConfirmPromptHost(
        viewModel = confirmViewModel,
        dialogEnabled = currentRoute != Route.SOS_COUNTDOWN &&
            currentRoute != Route.SOS_ACTIVE,
        onNavigateToSosCountdown = {
            val route = navController.currentBackStackEntry?.destination?.route
            if (route != Route.SOS_COUNTDOWN) {
                navController.navigate(Route.SOS_COUNTDOWN) {
                    launchSingleTop = true
                }
            }
        },
    )
    }
}

private fun handleSettingsNavigation(
    event: SettingsEvent,
    navController: androidx.navigation.NavHostController,
    onLogout: () -> Unit,
) {
    when (event) {
        SettingsEvent.NavigateToLogin -> onLogout()
        SettingsEvent.NavigateToProfile -> navController.navigate(DashboardRoutes.PROFILE)
        SettingsEvent.NavigateToPermissions -> navController.navigate(Route.SETTINGS_PERMISSIONS)
        SettingsEvent.NavigateToNotifications -> navController.navigate(Route.SETTINGS_NOTIFICATIONS)
        SettingsEvent.NavigateToSecurity -> navController.navigate(Route.SETTINGS_SECURITY)
        SettingsEvent.NavigateToAbout -> navController.navigate(Route.SETTINGS_ABOUT)
        SettingsEvent.NavigateToPrivacy -> navController.navigate(Route.SETTINGS_PRIVACY)
        SettingsEvent.NavigateToTerms -> navController.navigate(Route.SETTINGS_TERMS)
        SettingsEvent.NavigateToBattery -> navController.navigate(Route.SETTINGS_BATTERY)
        SettingsEvent.OpenAppSettings -> Unit
    }
}

@Composable
fun ComingSoonScreen(featureKey: String) {
    val title = when (featureKey) {
        QuickActionFeature.CONTACTS.routeKey -> stringResource(R.string.action_contacts)
        QuickActionFeature.SOS.routeKey -> stringResource(R.string.action_sos)
        QuickActionFeature.AI.routeKey -> stringResource(R.string.action_ai)
        QuickActionFeature.HELPERS.routeKey -> stringResource(R.string.action_helpers)
        QuickActionFeature.LIVE_LOCATION.routeKey -> stringResource(R.string.action_live_location)
        QuickActionFeature.SETTINGS.routeKey -> stringResource(R.string.action_settings)
        else -> stringResource(R.string.coming_soon_title)
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = title,
                style = MaterialTheme.typography.headlineSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.coming_soon_message),
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
            )
        }
    }
}
