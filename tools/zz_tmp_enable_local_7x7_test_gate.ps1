$ErrorActionPreference = 'Stop'

Write-Host "Runner machine: $env:COMPUTERNAME"
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    Write-Host 'No local backend is listening on port 8000 on this runner; leaving it unchanged.'
    exit 0
}

$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
Write-Host "Backend PID: $($listener.OwningProcess)"
Write-Host "Backend executable: $($proc.ExecutablePath)"
Write-Host "Backend command: $($proc.CommandLine)"

foreach ($repo in @('C:\GitHub\spina-lending-app-clean', 'C:\GitHub\spina-lending-app')) {
    if (Test-Path (Join-Path $repo '.git')) {
        Write-Host "Local repo: $repo"
        Write-Host "Local repo HEAD: $(git -C $repo rev-parse HEAD)"
        Write-Host "Local repo branch: $(git -C $repo branch --show-current)"
    }
}

$dbUrl = $env:GILBIC_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($dbUrl)) {
    foreach ($root in @('C:\GitHub', 'C:\SPINA_ONLINE')) {
        if (-not (Test-Path $root)) { continue }
        $files = Get-ChildItem -Path $root -Filter '.env' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 40
        foreach ($file in $files) {
            $line = Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue |
                Where-Object { $_ -match '^\s*GILBIC_DATABASE_URL\s*=' } |
                Select-Object -First 1
            if ($line) {
                $candidate = ($line -replace '^\s*GILBIC_DATABASE_URL\s*=\s*', '').Trim().Trim('"').Trim("'")
                if (-not [string]::IsNullOrWhiteSpace($candidate)) {
                    $dbUrl = $candidate
                    Write-Host "Using local backend database configuration from: $($file.DirectoryName)"
                    break
                }
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($dbUrl)) { break }
    }
}
if ([string]::IsNullOrWhiteSpace($dbUrl)) {
    $dbUrl = 'postgresql://127.0.0.1:5432/gilbic_dev'
    Write-Host 'Using backend default database URL for gilbic_dev.'
}

$python = $proc.ExecutablePath
if ([string]::IsNullOrWhiteSpace($python) -or -not (Test-Path $python)) {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
}

$scriptPath = Join-Path $env:RUNNER_TEMP 'spina_enable_local_7x7_test_gate.py'
$pythonCode = @'
import os
import psycopg
from psycopg.rows import dict_row

url = os.environ['SPINA_LOCAL_DB_URL']
with psycopg.connect(url) as conn:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute('select current_database() as db')
        db = cur.fetchone()['db']
        print(f'Connected local database: {db}')
        if db != 'gilbic_dev':
            raise RuntimeError(f'Refusing unexpected database {db!r}; expected gilbic_dev.')

        cur.execute("""
            select
              count(*) filter (
                where upper(c.full_name) like 'TEST CLIENT %'
                  and upper(c.area) = 'GILBIC TEST AREA'
              ) as test_active,
              count(*) filter (
                where not (
                  upper(c.full_name) like 'TEST CLIENT %'
                  and upper(c.area) = 'GILBIC TEST AREA'
                )
              ) as non_test_active
            from lending.loans l
            join lending.clients c on c.id = l.client_id
            join lending.loan_types lt on lt.id = l.loan_type_id
            where l.status = 'active'
              and c.status = 'active'
              and lt.calculation_mode = 'seven_by_seven'
        """)
        counts = cur.fetchone()
        test_active = int(counts['test_active'] or 0)
        non_test_active = int(counts['non_test_active'] or 0)
        print(f'Active 7x7 safety guard: test={test_active}, non_test={non_test_active}')
        if test_active < 1 or non_test_active != 0:
            raise RuntimeError('Safety guard failed: active 7x7 loans are not test-only.')

        cur.execute("""
            select id, daily_interest_per_1000
            from lending.loan_types
            where is_active = true and calculation_mode = 'seven_by_seven'
        """)
        loan_types = cur.fetchall()
        if len(loan_types) != 1:
            raise RuntimeError(f'Expected one active seven_by_seven loan type; found {len(loan_types)}.')
        loan_type = loan_types[0]
        if loan_type['daily_interest_per_1000'] is None or loan_type['daily_interest_per_1000'] <= 0:
            raise RuntimeError('7x7 daily interest basis is missing.')

        cur.execute("""
            update lending.loan_types
            set settings = jsonb_set(
              jsonb_set(
                jsonb_set(
                  coalesce(settings, '{}'::jsonb),
                  '{mobile_collections_enabled}', 'true'::jsonb, true
                ),
                '{mobile_seven_by_seven_enabled}', 'true'::jsonb, true
              ),
              '{mobile_balance_mode}', to_jsonb('direct_remaining_balance'::text), true
            )
            where id = %s
            returning settings
        """, (loan_type['id'],))
        settings = cur.fetchone()['settings']
        conn.commit()
        if settings.get('mobile_collections_enabled') is not True:
            raise RuntimeError('mobile_collections_enabled verification failed.')
        if settings.get('mobile_seven_by_seven_enabled') is not True:
            raise RuntimeError('mobile_seven_by_seven_enabled verification failed.')
        if settings.get('mobile_balance_mode') != 'direct_remaining_balance':
            raise RuntimeError('mobile_balance_mode verification failed.')
        print('LOCAL_7X7_TEST_GATE_ENABLED=true')
'@
Set-Content -LiteralPath $scriptPath -Value $pythonCode -Encoding utf8

$env:SPINA_LOCAL_DB_URL = $dbUrl
& $python $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw 'Guarded local 7x7 update failed.'
}
Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
