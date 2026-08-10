# Keep SafeHer release builds lean but preserve reflection-heavy libs.
-keepattributes Signature, InnerClasses, EnclosingMethod, RuntimeVisibleAnnotations
-keepattributes *Annotation*

# BuildConfig
-keep class com.safeher.app.BuildConfig { *; }

# Retrofit / Moshi
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-keep class com.safeher.app.data.remote.dto.** { *; }
-keep class com.squareup.moshi.** { *; }
-dontwarn com.squareup.moshi.**
-keep class kotlin.Metadata { *; }

# Hilt / Dagger
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }
-keep @dagger.hilt.android.HiltAndroidApp class *
-keep @dagger.hilt.android.AndroidEntryPoint class *
-keep @androidx.hilt.work.HiltWorker class * { *; }

# WorkManager
-keep class * extends androidx.work.Worker
-keep class * extends androidx.work.CoroutineWorker
-keep class androidx.work.WorkerParameters { *; }

# Google Maps / Play Services
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**
-keep class com.google.maps.android.** { *; }
-dontwarn com.google.maps.android.**

# Compose (runtime stability under R8)
-keep class androidx.compose.** { *; }
-dontwarn androidx.compose.**

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Timber
-dontwarn org.jetbrains.annotations.**

# TensorFlow Lite
-keep class org.tensorflow.lite.** { *; }
-dontwarn org.tensorflow.lite.**

# Firebase / Crashlytics
-keepattributes SourceFile,LineNumberTable
-keep public class * extends java.lang.Exception
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# EncryptedSharedPreferences
-keep class androidx.security.crypto.** { *; }
