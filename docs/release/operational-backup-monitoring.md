# Operational backup and monitoring preparation

The small wrappers in `ops/digitalocean` use PostgreSQL, tar, restic and systemd.
The owner selected **this Windows PC only for now** on 29 September 2026. The
source examples remain disabled; actual activation evidence is recorded separately.
No paid storage is required. A configured schedule is not evidence of a completed
off-host copy, delivered alert, accepted recovery objective or performance budget.

## Owner choices and proposed defaults

| Required choice | Concrete proposal, awaiting acceptance |
| --- | --- |
| Repository | Selected: dedicated encrypted PC repository `C:/Users/pc/SpinaBackups/repository`; root-private encrypted server staging repository `/var/lib/spina-backup/repository` |
| Schedule | Daily 03:00 Manila, with up to ten minutes of jitter |
| Retention | Seven daily, four weekly and three monthly recovery points, scoped to the dedicated repository/host/tag; existing archives are untouched |
| Integrity | Metadata check after every upload; full encrypted data read weekly, Monday 04:00 Manila; isolated logical restore monthly and after material schema/storage changes |
| Alerts | Named owner email through the selected authenticated SMTP provider, verifying TLS; test actual receipt before enabling |
| Proposed alert thresholds | Two-minute checks; disk at 85%; last complete backup older than 30 hours; at least three 5xx and at least 5% of captured requests in five minutes; failed backup/integrity service |
| Recovery key | Separate protected restic password, with independent recovery custody usable after losing this server and this PC |
| RPO and RTO | Owner must accept maximum lost work and recovery time; the schedule and rehearsal timings do not establish either |

Restic supplies encryption, authenticated content, repository locking, retention
and restore verification. See its [backup](https://restic.readthedocs.io/en/stable/040_backup.html),
[integrity](https://restic.readthedocs.io/en/stable/045_working_with_repos.html),
[retention](https://restic.readthedocs.io/en/stable/060_forget.html) and
[restore](https://restic.readthedocs.io/en/stable/050_restore.html) documentation.
The wrapper uses stable flags available in restic 0.16 or newer.

## Selected Windows PC workflow

`pull-backup.ps1` first uses the existing independently pinned SSH identity to
start `spina-backup.service`. It then uses restic's SFTP transport to copy matching
encrypted snapshots to the dedicated PC repository, reads/authenticates all
copied data, checks freshness and applies scoped retention. A private
`last-success.json` is replaced only after every step succeeds. Native diagnostics
are suppressed from public output. A repository identity marker prevents an
accidental retention run against an unmarked or different repository.

Only verified PC completion updates the server's separate `pc-last-success` and
`pc-last-result` markers. Failure attempts to record a fixed `failed` result;
an unreachable PC/host leaves the old success timestamp to expire. With
`SPINA_MONITOR_PC_BACKUP_REQUIRED=yes`, a fresh server staging snapshot cannot
mask a failed, missing or stale PC copy. This provides a checkable condition;
actual notification still depends on an activated recipient/channel.

Use `pc-backup.example.json` as the schema. Runtime, binaries, pinned key/known
hosts, configuration, DPAPI passwords and state belong under
`C:/Users/pc/SpinaBackups/operations`, restricted to the current `pc` account,
and SYSTEM. Store two independently generated passwords with
Windows `ConvertFrom-SecureString` under that account: `PasswordDpapiFile` for
the PC repository and `SourcePasswordDpapiFile` for server staging. The script
uses the dedicated `restic-password.ps1` provider through restic's private
password-command pipe; no plaintext password file is created. Never invoke that
provider directly in a terminal or diagnostic capture: its stdout is a password.
The server's source password is `/root/spina-backup-source-password`, mode `0600`,
outside every captured path. DPAPI protection is tied to this Windows identity;
an independently usable recovery-key copy is still required. Keep this runtime
outside AppData: packaged Windows apps can redirect AppData writes into their
private package cache, making the apparent path invisible to Task Scheduler.
Verify the actual scheduled process can read its files under the intended user.

Before the first run, explicitly initialize both dedicated repositories. Create
`repository/spina-pc-backup.json` with `kind: "spina-pc-restic-v1"` and a fresh
random `id`, and put the same value in `RepositoryId`. Neither wrapper creates
repositories or identity markers. Use the protected source configuration with
`RESTIC_REPOSITORY=/var/lib/spina-backup/repository`, no cloud credentials and
the source password path above. Install the server backup service and its files;
the PC task invokes it, so a duplicate server backup timer is unnecessary.

After an actual end-to-end run and isolated restore, register a Windows Task
Scheduler task at 03:00 Manila for the current `pc` user, interactive logon,
`StartWhenAvailable`, and no concurrent instances. Run PowerShell with
`-NoProfile -NonInteractive -WindowStyle Hidden -File <private-runtime>/pull-backup.ps1 -ConfigPath
<private-runtime>/pc-backup.json`. Confirm the machine timezone used by the
trigger. Retain the task's next run, last result and PC success marker. A locked
screen is fine while that account is logged in; a powered-off, disconnected or
logged-out PC delays copying until it is available. Server staging alone does
not protect against server loss. Record this availability limit separately from
any accepted RPO, and periodically restore using the PC repository and separately
held recovery key.

The generic server-only timer examples below remain optional preparation. They
must not be treated as proof that the selected PC copy ran. Off-host copy-age
alerting still needs an actual available recipient/channel; SMTP credentials
are not implied by a connected mailbox in Codex.

## Capture boundary

`backup.sh` takes the same `/opt/spina/deployment.lock` as deployment. It checks
repository/key access before stopping an active API, then captures a custom-format
database dump and archives private evidence, `/etc/spina`, the selected release's
`runtime.env` and `git-sha`, Caddy configuration and the API unit. Archives preserve
tar file metadata and symlinks. The configured private root must match the actual
application root. Missing inputs, unreadable files and partial restic backups fail.

The API resumes immediately after local capture, before off-host upload. EXIT,
INT and TERM handling attempts to resume it on failure; systemd `ExecStopPost`
uses the private pause marker to recover after a killed job. A host crash still
requires normal service startup and operator verification. Capture temporarily
interrupts API requests: approve that maintenance window before activation.

PostgreSQL supplies a consistent logical snapshot. A consistent pair with files
also requires all writers to those files and application tables to be quiescent.
The operator must confirm that stopping this API covers every relevant writer;
other deployments, jobs or direct database writers must be coordinated separately.
This is not PITR, an OS image or full restoration of a managed Supabase service.
See [PostgreSQL's dump scope](https://www.postgresql.org/docs/18/app-pgdump.html)
and the retained actual recovery rehearsal for managed objects and exclusions.

Only the script's own fresh staging directory is removed. Existing recovery
archives, protected old working copies, private evidence and rollback releases
are never cleanup targets. The temporary dump is private plaintext until its
encrypted upload completes. The restic key and PostgreSQL password file belong
outside captured paths (the examples use `/root`), with `0600` permissions. Do
not place the encryption key under `/etc/spina` or the private evidence root.

## Activation procedure

1. Record the selected PC destination, backup and alert owners, independent key
   custody, frequency, retention, maintenance window and recovery objectives.
   Confirm restoration access. Preserve the existing verified
   independent recovery archives.
2. Install distribution PostgreSQL client, restic, tar and Python. Use a pg_dump
   compatible with the server. Copy `backup.sh` and `tools/check_operational_health.py`
   to root-owned `/opt/spina-operations` with modes `0755` and `0644`; create
   `/var/lib/spina-backup`, `/var/lib/spina-monitor` and `/var/cache/spina-restic`
   as root `0700`.
3. Fill the two `.env.example` files into `/etc/spina/backup.env` and
   `/etc/spina/monitor.env` as root `0600`. Supply actual repository credentials,
   verified-TLS PostgreSQL settings and private `PGPASSFILE`. Do not source these
   systemd environment files in a shell or print them. Validate exact source paths.
4. Initialize only the approved dedicated repository using a one-shot systemd
   job with `EnvironmentFile=/etc/spina/backup.env` and `/usr/bin/restic init`.
   The backup wrapper never initializes a repository itself. Keep
   `SPINA_BACKUP_RETENTION_ENABLED=no` until the retention preview is reviewed.
5. Copy the six `.service`/`.timer` files to `/etc/systemd/system`; run
   `systemd-analyze verify` and `systemctl daemon-reload`. Set
   `SPINA_BACKUP_ENABLED=yes` only after quiescence and maintenance approval.
   Start one `spina-backup.service`, verify the API resumed, and inspect the
   restricted `last-snapshot.json` and `last-success` evidence. Restore this exact
   snapshot into a fresh isolated target using the procedure below.
6. Preview `restic forget` with the configured host, `spina-operational-v1` tag,
   `--group-by host,tags`, configured daily/weekly/monthly counts and `--dry-run`.
   Only after review set `SPINA_BACKUP_RETENTION_ENABLED=yes` if approved. The
   wrapper always scopes rotation to its configured host and tag.
7. Configure the real recipient and provider; set `SPINA_ALERT_ENABLED=yes`.
   Run the monitor once with `--test-alert` through the private environment.
   SMTP acceptance is not recipient receipt: record actual receipt separately.
   Then run a normal monitor check. No message should contain private paths,
   account IDs, records, credentials, HTTP bodies or raw errors.
8. Enable the three timers only after successful first backup, independent
   restore, tested alert receipt and owner acceptance. Retain timer status and
   sanitized evidence; review the first scheduled run. Never copy example blank
   credentials directly into an enabled service.

## Updating an installed monitor

The application release archive does not install operations scripts. When a
release changes `tools/check_operational_health.py`, update its separately
installed copy in `/opt/spina-operations` as an explicit release step. An
application revision check alone does not verify the running monitor version.

Read the reviewed file from the exact green source commit and compute its SHA256
with LF line endings. Check the existing installed hash against the expected
previous revision before changing it. Preserve that exact previous file privately
for rollback, compile and check the replacement's journal parser without external
calls, then atomically replace only the script as root with mode `0644`. Preserve
the environment, state, service and timer. A running invocation may finish using
the old code; the next timer invocation loads the replacement.

Record the source revision, installed hash, rollback copy and next successful
monitor run with sanitized health results. If verification fails, restore the
verified previous script atomically and investigate. This update does not require
a new backup, test email, API restart or recreation of existing schedules.

## Isolated restore and integrity check

Use the separately held key and approved repository credentials from an isolated
operator environment. Run `restic check --read-data`, then `restic restore` with
the exact reviewed snapshot ID, a fresh private `--target` directory and `--verify`.
Restic restores the four files `database.dump`, `private-evidence.tar`,
`configuration.tar` and `SHA256SUMS`. Verify every SHA256 before proceeding.
The configuration archive also includes the configured `PGSSLROOTCERT` public CA file by basename; restore it at the configured certificate path before using the captured `verify-full` database connection.

Run `pg_restore --list` first. Create an isolated empty database, recreate only
the reviewed roles/extensions/prerequisites, and use the existing actual recovery
runbook's managed-object exclusions where required. Restore with
`pg_restore --exit-on-error`. Never restore over production or bulk-replay the
historical migration registry. Extract private files and configuration only to
the isolated target, preserving ownership/modes and safely handling links.
Verify database row/schema manifests, linked storage keys and file hashes using
the existing [recovery drill checks](backup-restore-drill.md); exercise read-only
application access with external sending and financial writes disabled. Record
snapshot ID, hashes, source revision, exclusions, timings and cleanup. Restore
success must include the files referenced by the database, not just dump parsing.

Weekly `spina-backup-check` downloads and authenticates all encrypted repository
data. It can incur transfer charges and takes a repository lock; a conflict fails
and must be inspected/retried. It is an integrity check, not a logical restore.
Actual monthly restored-database/file acceptance remains an operator exercise.

## Monitoring limits

The monitor checks local liveness/readiness, the configured public HTTPS readiness
URL with certificate validation and no redirects, API/Caddy units, disk usage,
backup age, required PC-copy age/result, latest backup/integrity result, and sanitized structured request 5xx
counts. Logs are bounded to the latest 10,000 journal records in five minutes.
A recorded backup pause suppresses API/HTTPS checks for at most ten minutes;
stalled maintenance then alerts. Caddy service, disk and backup checks continue.

Alerts contain fixed check codes only. A changed failure set or recovery sends
an email; unchanged failures remind at most hourly. Failed delivery is retried
and never recorded as notified. No credentials are sent before verified SMTP TLS.
The host cannot email while it is powered off or fully isolated: an independent
external uptime/heartbeat monitor and its tested recipient remain necessary for
host-loss coverage. Local probes cannot establish client-network availability.

These preparation files do not make authenticated performance representative.
Continue using the existing [bounded performance probe](performance-acceptance.md)
with a real isolated identity provider, synthetic role accounts and confirmed
workload. The known host is one CPU/~1 GiB RAM; local Windows or mocked-auth
measurements cannot establish its production Auth/network/latency budget.
