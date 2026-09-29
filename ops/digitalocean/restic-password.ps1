param([Parameter(Mandatory = $true)][string]$ProtectedFile)

# Called ONLY by restic --password-command. Stdout is its private password pipe.
# Never run directly in a terminal, transcript, diagnostic tool or public log.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$secure = $null
$pointer = [IntPtr]::Zero
try {
    $secure = Get-Content -LiteralPath $ProtectedFile -Raw | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer))
    exit 0
}
catch {
    [Console]::Error.WriteLine('Protected backup password unavailable.')
    exit 1
}
finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
