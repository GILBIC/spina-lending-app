# Deployment and application recovery

This describes the existing DigitalOcean deployment prepared by the Priority 10
batch. It is a runbook, not evidence that a deployment or production recovery
occurred. Actual host, secret, monitoring and recovery owners must be recorded in
the release acceptance record. Native V1 acceptance remains Windows and Android.

## Release layout and operator settings

Each attempt creates `/opt/spina/releases/<git-sha>.<unique-suffix>/`. That final
directory contains its own Python virtual environment, installed backend packages,
portal build, `git-sha`, root-only `runtime.env`, service/Caddy configuration and
request logging configuration. It is never moved after creating the virtual
environment or overwritten by a subsequent attempt. `/opt/spina/current` selects
the API runtime and its generated environment; `/var/www/spina` selects the portal.

The service also reads `/etc/spina/operator.env`, owned by root with mode `0600`.
This file holds actual owner/staff configuration, private evidence location,
approved privacy and loan-template manifests, approved document converter, SMTP
and other operator settings. Do not put its values in GitHub, Notion, test
artifacts or logs. It is read after the generated environment, so an intentional
operator assignment takes precedence. Avoid duplicating generated database/Auth
credentials or CORS settings in it unless an operator deliberately owns that
override and the associated rotation process.

On the first upgrade, if no operator file exists, the bootstrap preserves the
non-generated assignments from the old `/etc/spina/spina.env`. It does not execute
those assignments, copy the old generated DB/Auth credentials, or overwrite an
existing operator file. Keep the old environment file until rollback to the
legacy service is no longer required. Later redeployments leave operator settings
unchanged. Any deliberate operator-setting change needs its own verified recovery
copy; application deployment does not roll that file backward.

`/var/lib/spina` is mode `0700` and owned by the service account `spina`. Configure
private evidence under this persistent directory and keep it outside all static
portal/release paths. Document retention and backups for these files separately
from the database. Do not delete this directory while pruning application releases.

## Activation and failed attempts

Normal workflow executions queue rather than cancel each other. Every attempt
uses a root-only `/var/lib/spina-deploy/run-<run-id>-<attempt>/` directory for its
archive, generated environment, immutable staged bootstrap, log and atomic
`exit-code` file. SSH launch retries use one claim directory and cannot spawn the
same attempt again. A manually cancelled workflow can leave its detached process
running, but a replacement attempt cannot overwrite that process's inputs or
mistake its completion for the replacement's completion.

The bootstrap validates the archive digest and its packaged source SHA against
immutable workflow arguments before consuming it. The host lock is acquired
before package setup; an overlapping detached attempt fails with its own status
and cleans only its own temporary credential file. A canceled runner cannot be
assumed to have stopped the host process: inspect that exact attempt's log/status
before retrying. Do not clear another attempt's launch/status files.

The bootstrap keeps first-boot package coordination, Caddy TLS, the firewall,
loopback-only Uvicorn, and systemd isolation. A host lock prevents overlapping
activation attempts. It builds the candidate runtime and validates candidate
service/Caddy configuration before changing the active deployment.

The generated service runs `gilbic_backend.release_preflight --profile runtime`
as `ExecStartPre` using the selected release interpreter and environment. Missing
required schema/configuration blocks service startup and triggers activation
rollback. This check is read-only and does not apply migrations, provision legal
facts, or replace the separate activation/production acceptance profile. Candidate
unit validation rewrites all current-release paths, including preflight and logging,
to the candidate's final directory before the active link is changed.

Immediately before activation it saves the prior API link, portal link, systemd
unit and Caddy configuration in a private
`/opt/spina/releases/.activation.<unique-suffix>/` directory. The snapshot files
are numbered `1` through `4` in that order. The old Python runtime and its generated
environment remain in their original release directory.

After switching the files/links, the bootstrap restarts the API, reloads Caddy and
requires local liveness plus database readiness. Failure, interruption by TERM/INT,
or any unsuccessful activation exit restores the saved files/links and restarts
the prior API. A failed first deployment stops/disables the candidate API and
removes paths that did not previously exist. A failed restoration emits
`rollback needs operator recovery` and retains a failing exit status.

Before recording success, the running API's systemd MainPID working directory,
the portal link, and the selected release's SHA must all agree. After public HTTPS
verification, the workflow repeats that read-only check with the expected SHA;
the evidence writer refuses a different active SHA. A healthy older process
therefore cannot stand in for the requested candidate merely because its health
endpoints respond.

An abrupt host loss or SIGKILL cannot run a shell recovery trap. Local health also
does not prove public DNS/TLS, all business prerequisites, external Auth, or real
device acceptance. The existing workflow separately checks public HTTPS. If that
later external check fails, the release must remain unaccepted and the operator
must inspect the host and select a compatible prior release for recovery.

## Operator recovery procedure

1. Identify the exact host, attempted SHA, previous accepted release and matching
   activation snapshot. Confirm no deployment is running. Preserve bootstrap and
   service logs; do not paste credentials or private records into the incident.
2. Stop `spina-api` to prevent new API mutations while investigating. If account or
   credential compromise is suspected, isolate public access at the host/provider
   and revoke affected sessions/credentials through their actual owners. Stopping
   the API does not cancel a request already committed or erase device queues.
3. Before restoring application state, verify schema compatibility and available
   database/private-file recovery points. This deployment never runs migrations
   or attempts reverse migrations. Never restore a database merely because a new
   application release failed its health check.
4. Restore the snapshot's four deployment paths as root, preserving symbolic links
   rather than copying their targets; reload systemd, restart the prior API and
   reload Caddy. For a legacy prior service, retain its unchanged environment and
   shared virtual environment until that service is retired. Do not delete either
   the current or prior release while making this selection.
5. Verify local and public health, the release SHA, the read-only release preflight,
   representative authorized reads and denied-role/device access. Check the real
   operator configuration and private evidence access. If secrets were rotated,
   the old generated environment may be invalid: the owner must securely install
   current credentials before reopening. A prior application version alone cannot
   roll back provider-side credential revocation.
6. Reopen only after the recorded acceptance checks pass. Let offline clients retry
   pending work through the existing idempotent endpoints; never manually insert
   a second payment/payroll transaction because the original response was lost.
   Record the incident, selected release and verification outcomes without secrets.

The snapshot and immutable release are application recovery aids. They do not
undo OS/package upgrades or provider changes, restore financial data, or replace
a tested database plus private-file backup/PITR procedure. Release pruning is an
operator task after validating the active and retained recovery release paths.

## Runtime logs and monitoring

The generated logging configuration enables the `gilbic.request` logger at INFO.
The backend emits a server-generated request ID, static route pattern, method,
status and duration. Uvicorn raw access logging is disabled, avoiding duplicate
request lines containing URL/query values. Operational Uvicorn logs remain in the
systemd journal. Application records, request bodies, authorization headers,
credential values and private proof notes must not be added to request logs.

The operator still needs to set journal retention, disk/health/error-rate alerts,
backup-age alerts and actual recipients, then record a successful alert test.
Correlated request logs and health checks alone do not constitute monitoring
acceptance or a promise of recovery time.

## Automated verification

`tests/test_deployment_recovery.py` executes the real lifecycle functions against
temporary files, with only `systemctl` replaced by a recorder. It covers operator
setting preservation, actual link/config/runtime restoration after an EXIT-trap
failure, first-activation cleanup, successful activation retention and INFO logger
configuration without raw access lines. Additional regressions cover two distinct
staged runs, SHA/archive mismatch rejection, independent completion and credential
cleanup, failure before activation, and API/portal/runtime revision disagreement.
The workflow shell and its interpolated remote launch command are syntax-checked
without executing any host action. Linux CI uses native symbolic links;
Windows Git Bash uses its POSIX link representation. The existing deployment
contract and `bash -n ops/digitalocean/bootstrap.sh` cover the preserved transport,
secret-file, first-boot and workflow requirements. None of these tests bootstrap
a host, invoke systemd, access production or prove live recovery acceptance.
