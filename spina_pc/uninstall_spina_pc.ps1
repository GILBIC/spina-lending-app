[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ShortcutName = "SPINA Lending.lnk"
$OwnedShortcuts = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) $ShortcutName),
    (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\$ShortcutName")
)

$Removed = 0
foreach ($ShortcutPath in $OwnedShortcuts) {
    if (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) {
        Remove-Item -LiteralPath $ShortcutPath -Force
        $Removed += 1
        Write-Host "Removed: $ShortcutPath"
    }
}

if ($Removed -eq 0) {
    Write-Host "No SPINA-owned shortcut was found."
}
else {
    Write-Host "SPINA PC app-mode shortcuts removed. Browser profile and SPINA server data were left unchanged."
}
