package com.safeher.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.safeher.app.R

private data class OpenSourceLibrary(
    val name: String,
    val license: String,
    val url: String,
)

private val bundledLibraries = listOf(
    OpenSourceLibrary("Jetpack Compose", "Apache License 2.0", "https://developer.android.com/jetpack/compose"),
    OpenSourceLibrary("AndroidX / Material 3", "Apache License 2.0", "https://github.com/androidx/androidx"),
    OpenSourceLibrary("Hilt (Dagger)", "Apache License 2.0", "https://github.com/google/dagger"),
    OpenSourceLibrary("Retrofit / OkHttp / Moshi", "Apache License 2.0", "https://github.com/square"),
    OpenSourceLibrary("Kotlin Coroutines", "Apache License 2.0", "https://github.com/Kotlin/kotlinx.coroutines"),
    OpenSourceLibrary("Google Play Services Location & Maps", "Google APIs Terms", "https://developers.google.com/maps"),
    OpenSourceLibrary("TensorFlow Lite", "Apache License 2.0", "https://github.com/tensorflow/tensorflow"),
    OpenSourceLibrary("Firebase (Messaging, Crashlytics)", "Google APIs Terms", "https://firebase.google.com/terms"),
    OpenSourceLibrary("Timber", "Apache License 2.0", "https://github.com/JakeWharton/timber"),
)

@Composable
fun OpenSourceLicensesScreen(
    contentPadding: PaddingValues = PaddingValues(),
) {
    Scaffold(modifier = Modifier.padding(contentPadding)) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    text = stringResource(R.string.settings_about_licenses),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = stringResource(R.string.settings_about_licenses_intro),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp, bottom = 8.dp),
                )
            }
            items(bundledLibraries) { library ->
                Text(
                    text = library.name,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = library.license,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = library.url,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                HorizontalDivider(modifier = Modifier.padding(top = 8.dp))
            }
        }
    }
}
