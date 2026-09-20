# Synthetic backup and restore drill

`tools/run_release_recovery_drill.py` proves that a real PostgreSQL dump and its
private evidence files restore together. It uses generated synthetic records on
an explicitly selected loopback PostgreSQL server. It does not back up production,
establish a production recovery time or recovery point, or authorize deployment.

## Run

Use a local, disposable PostgreSQL cluster and matching `pg_dump`/`pg_restore`
binaries. The coordinator owns starting and stopping that cluster. The tool only
creates and deletes its own two databases; it never enumerates or deletes stale
databases owned by another run.

Create a private UTF-8 file outside the repository with the administrative DSN,
including an explicit loopback host, port, `dbname=postgres`, and user. Example
for a local test cluster, with the actual local port substituted:

```text
host=127.0.0.1 port=55439 dbname=postgres user=postgres
```

If the test server needs a password, keep it in that private file. Do not put the
DSN in logs or command arguments. The tool ignores PostgreSQL endpoint/service
environment variables, rejects remote/multiple hosts, pins `localhost` to
loopback, and refuses other administrative database names. It does not read any
application or production connection environment variable.

From the repository root in PowerShell, using the project Python environment:

```powershell
$env:PYTHONPATH = "$((Get-Location).Path);$((Join-Path (Get-Location) 'gilbic_backend/src'));$((Join-Path (Get-Location) 'tools'))"
python tools/run_release_recovery_drill.py `
  --admin-dsn-file C:/private/local-drill-admin.txt `
  --allow-disposable `
  --pg-bin 'C:/Program Files/PostgreSQL/18/bin' `
  --output C:/private/release-recovery-evidence.json
```

On Linux, use the corresponding absolute PostgreSQL binary directory and set
`PYTHONPATH=.:gilbic_backend/src:tools`. The output is sanitized JSON and the exit
status is nonzero on failure. Credentials, DSNs and raw database rows are never
written to the report. The caller retains responsibility for the private input
DSN file and the explicitly requested output file.

## What is proved

1. Create two unpredictable `spina_recovery_source_*` and
   `spina_recovery_restore_*` databases from `template0`. Only names successfully
   created by this invocation are eligible for cleanup.
2. Reuse the existing disposable bootstrap and onboarding migration list to replay
   every current migration, currently 0001–0128, including the historical duplicate
   0018 filenames. Fail if a new migration is missing from the replay list. Record
   every migration filename and SHA256.
3. Seed linked synthetic user/device, collector role, borrower, loan, payment-proof
   metadata, employee profile and draft payroll rows. The private proof contains
   nonempty synthetic PDF bytes and uses the same `PrivateEvidenceStore` as the
   application. These fixtures prove storage relationships, not payroll policy or
   payment acceptance; no collection or accounting posting is performed.
4. Run actual `pg_dump --format=custom`, retain its SHA256/size, and copy the
   configured synthetic private evidence directory with a per-file hash/size
   manifest. This is a quiescent synthetic dataset; a live backup would need its
   own coordinated consistency procedure.
5. Run actual `pg_restore --exit-on-error` into the second fresh database, preserving
   database privileges, and restore the private files into a separate directory.
   Compare the migrated/restored schema dumps, including ACLs but excluding owners,
   comments and PostgreSQL's random psql restrict nonce. For view bodies, use
   PostgreSQL's own pretty deparser after matching the exact body in the dump;
   this preserves semantics when PostgreSQL flattens associative `AND` expressions
   during restore. No arbitrary parentheses, predicates or privileges are removed.
   Compare every application
   table's row count and canonical row-content hash. Check representative joins
   and read the restored file using the database's own storage key, hash and size;
   compare the returned content against the original synthetic bytes.
6. Deliberately modify a real restored employee row and require row verification to
   reject it, then roll back. Deliberately corrupt a restored file without changing
   its size and require the file hash check to reject it, then restore the original
   from the backup. A negative probe that fails to detect corruption fails the drill.
7. Close all connections, drop only databases created by this run, and remove the
   generated temporary directory in `finally`/context cleanup, including failed
   runs. A cleanup failure is a failed drill. The report says `passed` only after
   both database and temporary-file cleanup have completed.

The report includes backup/restore durations, hashes, all table counts/hashes,
linked-record counts, corruption rejection results and cleanup status. The dump,
synthetic rows and files are temporary and removed; the sanitized evidence report
is the retained artifact.

## Production acceptance remains separate

This drill does not validate off-host storage, encryption/key escrow, secret or
role recreation, database global objects, live write consistency, retained backup
rotation, production data volume, operator alerting, or a production restore into
an isolated host. Those need an owner-approved operational backup/restore exercise
with actual configuration before claiming production recovery readiness. Never
point this synthetic tool at a tunnel or proxy to production, even if its endpoint
looks like loopback.
