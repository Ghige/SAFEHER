package com.safeher.app.core.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.safeher.app.core.ui.NotificationPermissionEffect
import com.safeher.app.core.ui.RootViewModel
import com.safeher.app.feature.auth.LoginScreen
import com.safeher.app.feature.auth.OnboardingScreen
import com.safeher.app.feature.auth.OtpScreen
import com.safeher.app.feature.auth.RegisterScreen
import com.safeher.app.feature.auth.SessionExpiredScreen
import com.safeher.app.feature.auth.SplashScreen
import com.safeher.app.feature.dashboard.DashboardNavigation

@Composable
fun SafeHerNavGraph(
    navController: NavHostController,
    rootViewModel: RootViewModel = hiltViewModel(),
) {
    val sessionExpired by rootViewModel.authRepository.sessionExpired.collectAsStateWithLifecycle()

    LaunchedEffect(sessionExpired) {
        if (sessionExpired) {
            navController.navigate(Route.SESSION_EXPIRED) {
                popUpTo(0) { inclusive = true }
            }
            rootViewModel.authRepository.clearSessionExpiredFlag()
        }
    }

    NavHost(
        navController = navController,
        startDestination = Route.SPLASH,
    ) {
        composable(Route.SPLASH) {
            SplashScreen(
                onNavigate = { route ->
                    navController.navigate(route) {
                        popUpTo(Route.SPLASH) { inclusive = true }
                    }
                },
            )
        }

        composable(Route.ONBOARDING) {
            OnboardingScreen(
                onNavigateToLogin = {
                    navController.navigate(Route.LOGIN) {
                        popUpTo(Route.ONBOARDING) { inclusive = true }
                    }
                },
            )
        }

        composable(Route.LOGIN) {
            LoginScreen(
                onNavigateToHome = { navigateToHome(navController) },
                onNavigateToRegister = { navController.navigate(Route.REGISTER) },
                onNavigateToOtp = { phone ->
                    navController.navigate(Route.otp(phone))
                },
            )
        }

        composable(Route.REGISTER) {
            RegisterScreen(
                onNavigateToLogin = { navController.popBackStack() },
                onNavigateToOtp = { phone ->
                    navController.navigate(Route.otp(phone)) {
                        popUpTo(Route.LOGIN) { inclusive = false }
                    }
                },
            )
        }

        composable(
            route = Route.OTP,
            arguments = listOf(navArgument(Route.PHONE_ARG) { type = NavType.StringType }),
        ) {
            OtpScreen(
                onNavigateToHome = { navigateToHome(navController) },
            )
        }

        composable(Route.SESSION_EXPIRED) {
            SessionExpiredScreen(
                onNavigateToLogin = {
                    navController.navigate(Route.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                },
            )
        }

        composable(Route.HOME) {
            NotificationPermissionEffect()
            DashboardNavigation(
                onLogout = {
                    rootViewModel.logout {
                        navController.navigate(Route.LOGIN) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                },
            )
        }
    }
}

private fun navigateToHome(navController: NavHostController) {
    navController.navigate(Route.HOME) {
        popUpTo(0) { inclusive = true }
    }
}
