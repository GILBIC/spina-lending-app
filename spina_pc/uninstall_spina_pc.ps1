[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ShortcutName = "Spina.lnk"
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
    Write-Host "No Spina shortcut was found."
}
else {
    Write-Host "Spina shortcuts removed. Browser profile and server data were left unchanged."
}
