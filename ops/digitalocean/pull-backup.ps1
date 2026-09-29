param([string]$ConfigPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-CheckedNative {
    param([string]$Executable, [string[]]$Arguments)
    # Capture native diagnostics privately. Never copy repository/SSH errors to logs.
    $inherited = @{}
    foreach ($name in @('RESTIC_PASSWORD', 'RESTIC_PASSWORD_FILE', 'RESTIC_PASSWORD_COMMAND', 'RESTIC_FROM_PASSWORD', 'RESTIC_FROM_PASSWORD_FILE', 'RESTIC_FROM_PASSWORD_COMMAND')) {
        $inherited[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    try {
        $captured = & $Executable @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'Backup command failed; inspect the configured endpoint privately.' }
    }
    finally {
        foreach ($name in $inherited.Keys) { [Environment]::SetEnvironmentVariable($name, $inherited[$name], 'Process') }
    }
    return $captured
}

function Copy-SpinaSnapshot {
    param($Config, [string]$SftpCommand = '')
    $repository = [IO.Path]::GetFullPath($Config.Repository)
    $state = [IO.Path]::GetFullPath($Config.StateDirectory)
    $marker = Join-Path $repository 'spina-pc-backup.json'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw 'Dedicated repository marker is missing.' }
    $identity = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($identity.id -ne $Config.RepositoryId -or $identity.kind -ne 'spina-pc-restic-v1') {
        throw 'Dedicated repository identity mismatch.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repository 'config') -PathType Leaf)) {
        throw 'Restic repository must be initialized explicitly.'
    }
    foreach ($value in @($Config.KeepDaily, $Config.KeepWeekly, $Config.KeepMonthly)) {
        if ([int]$value -lt 1) { throw 'Retention counts must be positive.' }
    }
    [IO.Directory]::CreateDirectory($state) | Out-Null
    $common = @('--repo', $repository, '--password-command', $Config.PasswordCommand, '--cache-dir', (Join-Path $state 'cache'))
    if ($SftpCommand) {
        # Restic's repeatable -o flag parses CSV before interpreting key=value.
        # Quote the entire field and double embedded command/path quotes.
        $common += @('-o', ('"sftp.command=' + $SftpCommand.Replace('"', '""') + '"'))
    }
    $scope = @('--host', $Config.SnapshotHost, '--tag', 'spina-operational-v1')
    Invoke-CheckedNative $Config.ResticExe ($common + @('copy', '--from-repo', $Config.SourceRepository, '--from-password-command', $Config.SourcePasswordCommand) + $scope) | Out-Null
    Invoke-CheckedNative $Config.ResticExe ($common + @('check', '--read-data')) | Out-Null
    $snapshots = @(Invoke-CheckedNative $Config.ResticExe ($common + @('snapshots', '--json') + $scope) | Out-String | ConvertFrom-Json)
    if ($snapshots.Count -eq 0) { throw 'No matching snapshot was copied.' }
    $latest = $snapshots | Sort-Object { [DateTimeOffset]$_.time } -Descending | Select-Object -First 1
    $age = [DateTimeOffset]::UtcNow - [DateTimeOffset]$latest.time
    if ($age.TotalHours -lt -0.1 -or $age.TotalHours -gt [double]$Config.MaximumSnapshotAgeHours) {
        throw 'Copied snapshot is stale or its timestamp is invalid.'
    }
    if ($Config.RetentionEnabled -eq $true) {
        Invoke-CheckedNative $Config.ResticExe ($common + @('forget', '--group-by', 'host,tags', '--keep-daily', [string]$Config.KeepDaily, '--keep-weekly', [string]$Config.KeepWeekly, '--keep-monthly', [string]$Config.KeepMonthly, '--prune') + $scope) | Out-Null
    }
    $result = [ordered]@{
        status = 'passed'; captured_at = [DateTimeOffset]::UtcNow.ToString('o')
        snapshot_id = $latest.id; snapshot_time = $latest.time
        encrypted_local_copy_verified = $true; cloud_storage_used = $false
        independent_key_custody_proven = $false
    }
    $temporary = Join-Path $state 'last-success.new'
    $result | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination (Join-Path $state 'last-success.json') -Force
    return $result
}

function Invoke-SpinaPcBackup {
    param([string]$Path)
    $config = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($config.Enabled -ne $true) { throw 'PC backup is not enabled.' }
    if ($config.SshTarget -notmatch '^[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+$') { throw 'Invalid SSH target.' }
    if (-not $config.SourceRepository.StartsWith("sftp:$($config.SshTarget):/")) { throw 'Source must be the configured SSH host.' }
    foreach ($name in @('SshExe', 'SshKeyFile', 'KnownHostsFile', 'ResticExe', 'PowerShellExe', 'PasswordProvider', 'PasswordDpapiFile', 'SourcePasswordDpapiFile')) {
        if ($config.$name -match '["\r\n]' -or -not (Test-Path -LiteralPath $config.$name -PathType Leaf)) {
            throw 'Required private file or executable is missing or invalid.'
        }
    }
    $state = [IO.Path]::GetFullPath($config.StateDirectory)
    [IO.Directory]::CreateDirectory($state) | Out-Null
    $lock = $null
    $sshOptions = @('-i', $config.SshKeyFile, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', "UserKnownHostsFile=$($config.KnownHostsFile)", '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
    try {
        $lock = [IO.File]::Open((Join-Path $state 'run.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        $providerFormat = '"{0}" -NoProfile -NonInteractive -File "{1}" -ProtectedFile "{2}"'
        $destinationCommand = $providerFormat -f $config.PowerShellExe.Replace('\', '/'), $config.PasswordProvider.Replace('\', '/'), $config.PasswordDpapiFile.Replace('\', '/')
        $sourceCommand = $providerFormat -f $config.PowerShellExe.Replace('\', '/'), $config.PasswordProvider.Replace('\', '/'), $config.SourcePasswordDpapiFile.Replace('\', '/')
        $config | Add-Member -NotePropertyName PasswordCommand -NotePropertyValue $destinationCommand -Force
        $config | Add-Member -NotePropertyName SourcePasswordCommand -NotePropertyValue $sourceCommand -Force
        Invoke-CheckedNative $config.SshExe ($sshOptions + @($config.SshTarget, 'systemctl start spina-backup.service')) | Out-Null
        # Restic parses this command itself; quoted paths contain no embedded quotes.
        $ssh = $config.SshExe.Replace('\', '/')
        $key = $config.SshKeyFile.Replace('\', '/')
        $known = $config.KnownHostsFile.Replace('\', '/')
        $sftp = '"{0}" -i "{1}" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile={2}" -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 {3} -s sftp' -f $ssh, $key, $known, $config.SshTarget
        $result = Copy-SpinaSnapshot $config $sftp
        Invoke-CheckedNative $config.SshExe ($sshOptions + @($config.SshTarget, 'umask 077; date -u +%s > /var/lib/spina-backup/pc-last-success.new && mv /var/lib/spina-backup/pc-last-success.new /var/lib/spina-backup/pc-last-success && printf success > /var/lib/spina-backup/pc-last-result')) | Out-Null
        $result | ConvertTo-Json -Compress
    }
    catch {
        try {
            Invoke-CheckedNative $config.SshExe ($sshOptions + @($config.SshTarget, 'umask 077; printf failed > /var/lib/spina-backup/pc-last-result')) | Out-Null
        }
        catch { }
        throw
    }
    finally {
        if ($null -ne $lock) { $lock.Dispose() }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        if (-not $ConfigPath) { throw 'A private configuration file is required.' }
        Invoke-SpinaPcBackup $ConfigPath
        exit 0
    }
    catch {
        # Generic output prevents SSH/SMTP/repository diagnostics exposing secrets.
        Write-Output '{"status":"failed","last_good_backup_preserved":true}'
        exit 1
    }
}
