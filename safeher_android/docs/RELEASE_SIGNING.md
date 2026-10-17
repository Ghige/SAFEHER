# SafeHer Android — release signing (P0-6)

## Play / production keystore (human-held)

1. Generate **once**, store offline / in a secret manager — never commit:

```bat
keytool -genkeypair -v -storetype JKS -keystore release\safeher-release.jks -alias safeher -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=SafeHer, OU=Mobile, O=SafeHer, L=City, ST=State, C=IN"
```

2. Copy `keystore.properties.example` → `keystore.properties` (gitignored) and fill passwords + `storeFile=release/safeher-release.jks`.

3. Build AAB for Play Internal Testing:

```bat
gradlew.bat :app:bundleRelease
```

Signed AAB path: `app/build/outputs/bundle/release/app-release.aab`

APK (sideload / local smoke only):

```bat
gradlew.bat :app:assembleRelease
```

Expect a **signed** APK/AAB under `app/build/outputs/`, not `*-unsigned.apk`.

## Local upload keystore (pipeline smoke only)

`scripts/generate_local_upload_keystore.ps1` can create a **throwaway** JKS + `keystore.properties` for proving the Gradle signing path.  
That key is **not** for Play Store. Losing it only affects local sideload tests.

## Status rule

- Signing **pipeline** may be VERIFIED with a local upload keystore.  
- **Production Play signing** remains BLOCKED until the real release keystore exists outside the repo.
