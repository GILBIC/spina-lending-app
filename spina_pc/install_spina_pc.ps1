[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PortalUrl,

    [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"
$ShortcutName = "SPINA Lending.lnk"

function Resolve-SafePortalUri {
    param([string]$Value)

    try {
        $Uri = [System.Uri]::new($Value.Trim())
    }
    catch {
        throw "PortalUrl must be a valid absolute URL."
    }

    if (-not $Uri.IsAbsoluteUri) {
        throw "PortalUrl must be an absolute URL."
    }

    $LocalHosts = @("localhost", "127.0.0.1", "::1")
    if ($Uri.Scheme -ne "https" -and $LocalHosts -notcontains $Uri.Host) {
        throw "SPINA PC requires an HTTPS portal URL. HTTP is allowed only for localhost development."
    }

    return $Uri.AbsoluteUri.TrimEnd("/")
}

function Find-SupportedBrowser {
    $Candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
    )

    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }

    throw "Microsoft Edge or Google Chrome is required to install SPINA PC app mode."
}

function New-SpinaShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ShortcutPath,
        [Parameter(Mandatory = $true)]
        [string]$BrowserPath,
        [Parameter(Mandatory = $true)]
        [string]$SafePortalUrl
    )

    $Parent = Split-Path -Parent $ShortcutPath
    if (-not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }

    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $BrowserPath
    $Shortcut.Arguments = "--app=$SafePortalUrl --start-maximized"
    $Shortcut.WorkingDirectory = Split-Path -Parent $BrowserPath
    $Shortcut.Description = "SPINA Lending secure four-role workspace"
    $Shortcut.IconLocation = "$BrowserPath,0"
    $Shortcut.Save()
}

$SafePortalUrl = Resolve-SafePortalUri -Value $PortalUrl
$BrowserPath = Find-SupportedBrowser
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) $ShortcutName
$StartMenuShortcut = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\$ShortcutName"

New-SpinaShortcut -ShortcutPath $DesktopShortcut -BrowserPath $BrowserPath -SafePortalUrl $SafePortalUrl
New-SpinaShortcut -ShortcutPath $StartMenuShortcut -BrowserPath $BrowserPath -SafePortalUrl $SafePortalUrl

Write-Host "SPINA PC installed."
Write-Host "Portal: $SafePortalUrl"
Write-Host "Browser app host: $BrowserPath"
Write-Host "Desktop shortcut: $DesktopShortcut"
Write-Host "Start Menu shortcut: $StartMenuShortcut"
Write-Host "SPINA PC stores no database password or backend secret in the shortcut."

if ($StartAfterInstall) {
    Start-Process -FilePath $BrowserPath -ArgumentList "--app=$SafePortalUrl", "--start-maximized"
}
