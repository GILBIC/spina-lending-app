$ErrorActionPreference = 'Stop'
Write-Host "Runner machine: $env:COMPUTERNAME"
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    Write-Host 'No local backend is listening on port 8000 on this runner.'
    exit 0
}
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
Write-Host "Backend PID: $($listener.OwningProcess)"
Write-Host "Backend executable: $($proc.ExecutablePath)"
Write-Host "Backend command: $($proc.CommandLine)"

$repo = 'C:\GitHub\spina-lending-app-clean'
if (-not (Test-Path (Join-Path $repo '.git'))) { throw "Expected local repo missing: $repo" }
Write-Host "LOCAL_HEAD=$(git -C $repo rev-parse HEAD)"
Write-Host "LOCAL_BRANCH=$(git -C $repo branch --show-current)"
$status = git -C $repo status --porcelain
if ($status) {
    Write-Host 'LOCAL_STATUS_BEGIN'
    $status | ForEach-Object { Write-Host $_ }
    Write-Host 'LOCAL_STATUS_END'
} else {
    Write-Host 'LOCAL_STATUS=CLEAN'
}
Write-Host 'ROOT_CONTENTS_BEGIN'
Get-ChildItem -LiteralPath $repo -Force | Select-Object -ExpandProperty Name | ForEach-Object { Write-Host $_ }
Write-Host 'ROOT_CONTENTS_END'

$src = Join-Path $repo 'src'
$backendSrc = Join-Path $repo 'gilbic_backend\src'
Write-Host "ROOT_SRC_EXISTS=$(Test-Path $src)"
Write-Host "GILBIC_BACKEND_SRC_EXISTS=$(Test-Path $backendSrc)"
if (Test-Path $src) {
  Write-Host "ROOT_SRC_REAL=$((Get-Item -LiteralPath $src).FullName)"
  Get-ChildItem -LiteralPath $src -Force | Select-Object -First 20 -ExpandProperty Name | ForEach-Object { Write-Host "ROOT_SRC_ITEM=$_" }
}

$python = $proc.ExecutablePath
Push-Location $repo
try {
  & $python -c "import sys; sys.path.insert(0, r'src'); import gilbic_backend; print('IMPORTED_BACKEND='+str(gilbic_backend.__file__))"
} finally { Pop-Location }
