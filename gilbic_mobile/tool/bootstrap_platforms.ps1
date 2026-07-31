param(
    [string]$Organization = "com.gilbic"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot

try {
    flutter --version
    flutter create `
        --platforms=android,ios `
        --org $Organization `
        --project-name gilbic_mobile `
        .
    flutter pub get
    flutter analyze
    flutter test
}
finally {
    Pop-Location
}
