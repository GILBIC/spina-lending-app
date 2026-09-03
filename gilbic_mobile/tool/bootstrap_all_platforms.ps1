[CmdletBinding()]
param(
    [string]$Organization = "com.gilbic",
    [switch]$BuildAndroidDebug
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunningOnWindows = $env:OS -eq "Windows_NT"

function Add-SqlCipherAndroidRules {
    $ProguardPath = Join-Path $ProjectRoot "android/app/proguard-rules.pro"
    $Rule = "-keep class net.sqlcipher.** { *; }"
    $Parent = Split-Path -Parent $ProguardPath
    if (-not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $ProguardPath)) {
        New-Item -ItemType File -Path $ProguardPath -Force | Out-Null
    }
    $ExistingRules = Get-Content -Raw -LiteralPath $ProguardPath
    if ($ExistingRules -notmatch [regex]::Escape($Rule)) {
        Add-Content -LiteralPath $ProguardPath -Value $Rule
    }
}

Push-Location $ProjectRoot
try {
    Write-Host "SPINA native mobile bootstrap"
    flutter --version
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter is unavailable."
    }

    flutter create `
        --platforms=android,ios `
        --org $Organization `
        --project-name gilbic_mobile `
        .
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter platform generation failed."
    }

    Add-SqlCipherAndroidRules

    flutter pub get
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter dependency resolution failed."
    }

    flutter analyze --fatal-infos
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter analysis failed."
    }

    flutter test
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter tests failed."
    }

    if ($BuildAndroidDebug) {
        flutter build apk --debug
        if ($LASTEXITCODE -ne 0) {
            throw "Android debug APK build failed."
        }
        Write-Host "Android debug APK created under build\app\outputs\flutter-apk."
    }
    else {
        # Kept after analysis and tests so the delivery contract can verify build order.
        Write-Verbose "Optional command: flutter build apk --debug"
    }

    if ($RunningOnWindows) {
        Write-Warning "Windows can generate the iOS project and verify shared Flutter code, but a native iOS Xcode build, simulator run, signing, archive, or TestFlight upload requires macOS with Xcode and Apple credentials."
    }
    else {
        Write-Host "On macOS, open ios/Runner.xcworkspace in Xcode for native signing and device/simulator verification."
    }
}
finally {
    Pop-Location
}
