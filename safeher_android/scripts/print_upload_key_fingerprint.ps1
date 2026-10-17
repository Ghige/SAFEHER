# SafeHer — print upload-key fingerprints without exposing passwords.
# Does NOT upload to Play. Does NOT print storePassword / keyPassword.

$ErrorActionPreference = "Stop"
$AndroidRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PropsPath = Join-Path $AndroidRoot "keystore.properties"
if (-not (Test-Path $PropsPath)) {
    Write-Host "NOT VERIFIED: keystore.properties missing (expected for CI clones)."
    Write-Host "Create it from keystore.properties.example. Never commit it."
    exit 2
}

$props = @{}
Get-Content $PropsPath -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim().TrimStart([char]0xFEFF)
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $idx = $line.IndexOf("=")
        $props[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim()
    }
}

$storeRel = $props["storeFile"]
$alias = $props["keyAlias"]
$storePass = $props["storePassword"]
if (-not $storeRel -or -not $alias -or -not $storePass) {
    Write-Host "NOT VERIFIED: keystore.properties incomplete (need storeFile, keyAlias, storePassword)."
    exit 2
}

$store = Join-Path $AndroidRoot $storeRel
if (-not (Test-Path $store)) {
    Write-Host "NOT VERIFIED: storeFile not found: $storeRel"
    exit 2
}

$Keytool = Join-Path ${env:ProgramFiles} "Android\Android Studio\jbr\bin\keytool.exe"
if (-not (Test-Path $Keytool)) { $Keytool = "keytool" }

Write-Host "storeFile=$storeRel"
Write-Host "keyAlias=$alias"
Write-Host "storeExists=true"
Write-Host "(passwords omitted)"

$ErrorActionPreference = "Continue"
& $Keytool -list -v -keystore $store -alias $alias -storepass $storePass 2>&1 |
    Select-String -Pattern "Alias name|Creation date|Entry type|SHA256:|SHA1:|Valid from" |
    ForEach-Object { $_.Line.Trim() }
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Play Console: compare SHA-256 with the App signing / Upload key certificate."
Write-Host "If this is release/safeher-upload-local.jks it is a LOCAL smoke key, not Play."
