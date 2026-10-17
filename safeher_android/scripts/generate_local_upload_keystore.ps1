# Generate a LOCAL-ONLY upload keystore for P0-6 signing pipeline smoke.
# NOT for Play Store. Files are gitignored (*.jks, keystore.properties).
# AI_AUTO_SOS stays false via BuildConfig — this script does not touch it.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app\build.gradle.kts"))) {
    # script lives in safeher_android/scripts
    $Root = Split-Path -Parent $PSScriptRoot
}
# Prefer repo android root = parent of scripts/
$AndroidRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $AndroidRoot

$ReleaseDir = Join-Path $AndroidRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

$Keystore = Join-Path $ReleaseDir "safeher-upload-local.jks"
$Props = Join-Path $AndroidRoot "keystore.properties"
$Keytool = Join-Path ${env:ProgramFiles} "Android\Android Studio\jbr\bin\keytool.exe"
if (-not (Test-Path $Keytool)) {
    $Keytool = "keytool"
}

$StorePass = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
$KeyPass = $StorePass
$Alias = "safeher"

if (Test-Path $Keystore) {
    Write-Host "Keystore already exists: $Keystore (reusing)"
} else {
    & $Keytool -genkeypair -v -storetype JKS `
        -keystore $Keystore `
        -alias $Alias `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -storepass $StorePass -keypass $KeyPass `
        -dname "CN=SafeHer Local Upload, OU=Dev, O=SafeHer, L=Local, ST=NA, C=IN"
    if ($LASTEXITCODE -ne 0) { throw "keytool failed" }
}

# Relative path from android project root
$RelStore = "release/safeher-upload-local.jks"
@"
storeFile=$RelStore
storePassword=$StorePass
keyAlias=$Alias
keyPassword=$KeyPass
"@ | ForEach-Object {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Props, $_, $utf8NoBom)
}

Write-Host "Wrote $Props (gitignored)"
Write-Host "Next: .\\gradlew.bat :app:assembleRelease"
Write-Host "NOTE: This is a local upload key — not Play production."
