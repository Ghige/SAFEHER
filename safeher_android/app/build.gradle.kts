import java.util.Properties
import java.io.File

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    alias(libs.plugins.google.services)
    alias(libs.plugins.firebase.crashlytics)
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val mapsApiKey: String = localProperties.getProperty("MAPS_API_KEY") ?: ""

/** Debug-only LAN URL for a physical device on the same Wi-Fi as the PC. Never used in release. */
fun normalizeDebugBaseUrl(raw: String): String {
    val trimmed = raw.trim().trim('"')
    if (trimmed.isEmpty()) return ""
    return if (trimmed.endsWith("/")) trimmed else "$trimmed/"
}

fun quotedBuildConfigString(value: String): String =
    "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

val debugApiBaseUrlOverride: String =
    normalizeDebugBaseUrl(localProperties.getProperty("DEBUG_API_BASE_URL") ?: "")
val emulatorDebugBaseUrl = "http://10.0.2.2:8000/"
val debugBaseUrl: String = debugApiBaseUrlOverride.ifEmpty { emulatorDebugBaseUrl }

val keystoreProperties = Properties().apply {
    val file = rootProject.file("keystore.properties")
    if (file.exists()) {
        // Manual parse: Java Properties + UTF-8 BOM from PowerShell breaks the first key.
        file.readText(Charsets.UTF_8)
            .removePrefix("\uFEFF")
            .lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("#") && it.contains("=") }
            .forEach { line ->
                val idx = line.indexOf('=')
                val key = line.substring(0, idx).trim().trimStart('\uFEFF')
                val value = line.substring(idx + 1).trim()
                if (key.isNotEmpty()) {
                    setProperty(key, value)
                }
            }
    }
}

android {
    namespace = "com.safeher.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.safeher.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "2.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("String", "BASE_URL", "\"http://10.0.2.2:8000/\"")
        buildConfigField("boolean", "ENABLE_LOGGING", "true")
        // Stage 0/1: automatic AI SOS stays OFF. Manual SOS is unaffected.
        // Release builds HARD-CODE false below — do not rely on this default alone.
        buildConfigField("boolean", "AI_AUTO_SOS_ENABLED", "false")
        buildConfigField("boolean", "DEMO_MODE", "true")
        buildConfigField("String", "MAPS_API_KEY", "\"$mapsApiKey\"")
        manifestPlaceholders["MAPS_API_KEY"] = mapsApiKey
    }

    signingConfigs {
        if (keystoreProperties.isNotEmpty()) {
            val storePath = keystoreProperties.getProperty("storeFile")
                ?: error("keystore.properties missing storeFile")
            create("release") {
                storeFile = rootProject.file(storePath)
                storePassword = keystoreProperties.getProperty("storePassword")
                    ?: error("keystore.properties missing storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                    ?: error("keystore.properties missing keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                    ?: error("keystore.properties missing keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            isDebuggable = true
            // Emulator always uses EMULATOR_DEBUG_BASE_URL (10.0.2.2).
            // Physical device uses DEBUG_API_BASE_URL from local.properties when set.
            buildConfigField("String", "BASE_URL", quotedBuildConfigString(debugBaseUrl))
            buildConfigField(
                "String",
                "DEBUG_API_BASE_URL",
                quotedBuildConfigString(debugApiBaseUrlOverride),
            )
            buildConfigField("String", "EMULATOR_DEBUG_BASE_URL", quotedBuildConfigString(emulatorDebugBaseUrl))
            buildConfigField("boolean", "ENABLE_LOGGING", "true")
            buildConfigField("boolean", "AI_AUTO_SOS_ENABLED", "false")
            buildConfigField("boolean", "DEMO_MODE", "true")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            buildConfigField("String", "BASE_URL", "\"https://api.safeher.app/\"")
            buildConfigField("String", "DEBUG_API_BASE_URL", "\"\"")
            buildConfigField("String", "EMULATOR_DEBUG_BASE_URL", "\"\"")
            buildConfigField("boolean", "ENABLE_LOGGING", "false")
            // HARD RULE (Stage 0/1 sign-off): release APK/AAB must ship with AI auto SOS OFF.
            // Changing this to true requires written product/security sign-off AFTER Stage 2+ gates.
            // Do NOT read this from a Gradle property for release — prevent accidental enable.
            buildConfigField("boolean", "AI_AUTO_SOS_ENABLED", "false")
            buildConfigField("boolean", "DEMO_MODE", "true")
            if (keystoreProperties.isNotEmpty()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

// Stage 0/1 guard: release (and any build type) must not enable AI auto SOS
// unless an explicit non-release experiment property is set. Release is never allowed.
afterEvaluate {
    val app = extensions.getByName("android") as com.android.build.gradle.BaseExtension
    app.buildTypes.forEach { buildType ->
        val raw = buildType.buildConfigFields["AI_AUTO_SOS_ENABLED"]?.value ?: "missing"
        val flag = raw.trim().trim('"')
        if (buildType.name == "release" && flag != "false") {
            throw GradleException(
                "Release buildType must keep AI_AUTO_SOS_ENABLED=false (found $raw). " +
                    "Requires Stage 2+ product sign-off to change.",
            )
        }
        if (flag == "true") {
            throw GradleException(
                "AI_AUTO_SOS_ENABLED=true blocked for buildType=${buildType.name}. " +
                    "Stage 0/1 requires false; enable only after written Stage 2+ sign-off.",
            )
        }
        val demo = (buildType.buildConfigFields["DEMO_MODE"]?.value ?: "missing").trim().trim('"')
        if (demo != "true") {
            throw GradleException(
                "DEMO_MODE must remain true for buildType=${buildType.name} (found $demo).",
            )
        }
        if (buildType.name == "release") {
            val base = (buildType.buildConfigFields["BASE_URL"]?.value ?: "").replace("\\\"", "")
            if (!base.contains("https://api.safeher.app/")) {
                throw GradleException("Release BASE_URL must be https://api.safeher.app/")
            }
            val logging = (buildType.buildConfigFields["ENABLE_LOGGING"]?.value ?: "").trim().trim('"')
            if (logging != "false") {
                throw GradleException("Release ENABLE_LOGGING must be false")
            }
        }
    }
}

fun tfliteCandidates(): List<File> {
    val repoRoot = rootProject.projectDir.parentFile
    return listOf(
        file("src/main/assets/yamnet_distress_quant.tflite"),
        repoRoot.resolve("safeher_ai/models/final/yamnet_distress_quant.tflite"),
        repoRoot.resolve("safeher_backend/app/ai/audio_model/yamnet_distress_quant.tflite"),
    )
}

tasks.register("syncTfliteAsset") {
    doLast {
        val dest = file("src/main/assets/yamnet_distress_quant.tflite")
        dest.parentFile.mkdirs()
        val src = tfliteCandidates().firstOrNull { it.isFile && it.length() > 1_000_000L }
            ?: error(
                "yamnet_distress_quant.tflite missing. Place the licensed export in " +
                    "app/src/main/assets/ or safeher_ai/models/final/.",
            )
        if (dest.canonicalPath != src.canonicalPath) {
            src.copyTo(dest, overwrite = true)
        }
        if (dest.length() < 1_000_000L) {
            error("TFLite asset too small: ${dest.length()} bytes")
        }
    }
}

tasks.matching { it.name == "preBuild" }.configureEach {
    dependsOn("syncTfliteAsset")
}

gradle.taskGraph.whenReady {
    val needsReleaseKey = gradle.taskGraph.allTasks.any { task ->
        val n = task.name
        n.contains("Release", ignoreCase = true) &&
            !n.contains("UnitTest", ignoreCase = true) &&
            (n.contains("assemble") || n.contains("bundle") || n.contains("package"))
    }
    if (needsReleaseKey) {
        if (keystoreProperties.isEmpty()) {
            throw GradleException(
                "Release AAB/APK requires keystore.properties (gitignored). " +
                    "See docs/RELEASE_SIGNING.md — do not commit passwords.",
            )
        }
        val storePath = keystoreProperties.getProperty("storeFile")
            ?: throw GradleException("keystore.properties missing storeFile")
        val store = rootProject.file(storePath)
        if (!store.isFile) {
            throw GradleException("Release keystore file not found at $storePath")
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.hilt.navigation.compose)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.work)
    ksp(libs.hilt.work.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.moshi)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.moshi)
    implementation(libs.moshi.kotlin)
    ksp(libs.moshi.codegen)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.security.crypto)

    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.work.runtime)

    implementation(libs.play.services.location)
    implementation(libs.play.services.maps)
    implementation(libs.maps.compose)
    implementation(libs.kotlinx.coroutines.play.services)

    implementation(libs.timber)
    implementation(libs.tensorflow.lite)
    implementation(libs.tensorflow.lite.select.tf.ops)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)
    implementation(libs.firebase.crashlytics)

    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    testImplementation(libs.junit)
    testImplementation(libs.truth)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
}
