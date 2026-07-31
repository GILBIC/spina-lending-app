param(
    [string]$Organization = "com.gilbic"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot

function Add-SqlCipherAndroidRules {
    $ProguardPath = Join-Path $ProjectRoot "android/app/proguard-rules.pro"
    $Rule = "-keep class net.sqlcipher.** { *; }"

    if (-not (Test-Path $ProguardPath)) {
        New-Item -ItemType File -Path $ProguardPath -Force | Out-Null
    }
    $ExistingRules = Get-Content -Raw -Path $ProguardPath
    if ($ExistingRules -notmatch [regex]::Escape($Rule)) {
        Add-Content -Path $ProguardPath -Value $Rule
    }

    $KotlinGradle = Join-Path $ProjectRoot "android/app/build.gradle.kts"
    if (Test-Path $KotlinGradle) {
        $Content = Get-Content -Raw -Path $KotlinGradle
        if ($Content -notmatch "proguard-rules\.pro") {
            $Replacement = "release {`r`n            proguardFiles(getDefaultProguardFile(`"proguard-android-optimize.txt`"), `"proguard-rules.pro`")"
            $Content = [regex]::Replace(
                $Content,
                "release\s*\{",
                $Replacement,
                1
            )
            Set-Content -Path $KotlinGradle -Value $Content -NoNewline
        }
        return
    }

    $GroovyGradle = Join-Path $ProjectRoot "android/app/build.gradle"
    if (Test-Path $GroovyGradle) {
        $Content = Get-Content -Raw -Path $GroovyGradle
        if ($Content -notmatch "proguard-rules\.pro") {
            $Replacement = "release {`r`n            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'"
            $Content = [regex]::Replace(
                $Content,
                "release\s*\{",
                $Replacement,
                1
            )
            Set-Content -Path $GroovyGradle -Value $Content -NoNewline
        }
    }
}

try {
    flutter --version
    flutter create `
        --platforms=android,ios `
        --org $Organization `
        --project-name gilbic_mobile `
        .
    Add-SqlCipherAndroidRules
    flutter pub get
    flutter analyze
    flutter test
}
finally {
    Pop-Location
}
