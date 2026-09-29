#!/usr/bin/env bash
# Operator-configured PostgreSQL + private-file snapshot. No repository creation.
set -Eeuo pipefail
umask 077

fail() { printf '%s\n' "spina backup failed: $1" >&2; exit 1; }
SERVICE=${SPINA_BACKUP_SERVICE:-spina-api}
if [[ "${1:-}" == --resume ]]; then
  [[ -n "${SPINA_BACKUP_STATE:-}" ]] || fail 'state configuration missing'
  if [[ -f "$SPINA_BACKUP_STATE/api-paused" ]]; then
    systemctl start "$SERVICE" >/dev/null 2>&1 || fail 'API restart failed'
    rm -- "$SPINA_BACKUP_STATE/api-paused"
  fi
  exit 0
fi
[[ "${SPINA_BACKUP_ENABLED:-no}" == yes ]] || fail 'not enabled by operator'
for name in RESTIC_REPOSITORY RESTIC_PASSWORD_FILE PGHOST PGPORT PGDATABASE PGUSER \
  SPINA_BACKUP_STATE SPINA_BACKUP_PRIVATE_ROOT SPINA_BACKUP_CONFIG_ROOT SPINA_BACKUP_HOST \
  SPINA_BACKUP_KEEP_DAILY SPINA_BACKUP_KEEP_WEEKLY SPINA_BACKUP_KEEP_MONTHLY; do
  [[ -n "${!name:-}" ]] || fail 'required configuration missing'
done
for name in SPINA_BACKUP_KEEP_DAILY SPINA_BACKUP_KEEP_WEEKLY SPINA_BACKUP_KEEP_MONTHLY; do
  [[ "${!name}" =~ ^[1-9][0-9]*$ ]] || fail 'retention counts must be positive'
done
[[ -f "$RESTIC_PASSWORD_FILE" ]] || fail 'key file missing'
[[ "$PGHOST" == 127.0.0.1 || "$PGHOST" == ::1 || "${PGSSLMODE:-}" == verify-full ]] || fail 'remote PostgreSQL requires verified TLS'
[[ -d "$SPINA_BACKUP_PRIVATE_ROOT" && -d "$SPINA_BACKUP_CONFIG_ROOT" ]] || fail 'capture source missing'
for command in restic pg_dump pg_restore tar sha256sum flock systemctl realpath; do
  command -v "$command" >/dev/null || fail 'required executable missing'
done
KEY_PATH=$(realpath "$RESTIC_PASSWORD_FILE")
for name in SPINA_BACKUP_PRIVATE_ROOT SPINA_BACKUP_CONFIG_ROOT; do
  SOURCE_PATH=$(realpath "${!name}")
  [[ "$KEY_PATH" != "$SOURCE_PATH" && "$KEY_PATH" != "$SOURCE_PATH"/* ]] || fail 'encryption key must be outside captured directories'
done
mkdir -p "$SPINA_BACKUP_STATE"
chmod 700 "$SPINA_BACKUP_STATE"
# Same lock as deployment: a snapshot must not cross a release activation.
exec 9>"${SPINA_BACKUP_LOCK:-/opt/spina/deployment.lock}"
flock -n 9 || fail 'another backup or deployment is running'
WORK=$(mktemp -d "$SPINA_BACKUP_STATE/run.XXXXXXXX")
PAUSED=no
cleanup() {
  local result=$?
  trap - EXIT INT TERM
  if [[ "$PAUSED" == yes ]]; then
    if systemctl start "$SERVICE" >/dev/null 2>&1; then
      rm -f -- "$SPINA_BACKUP_STATE/api-paused"
    else
      result=1
    fi
  fi
  # Only this invocation's mktemp directory is eligible for removal.
  [[ "$WORK" == "$SPINA_BACKUP_STATE"/run.* && -d "$WORK" ]] && rm -rf -- "$WORK"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 1' INT TERM
run() { "$@" >"$WORK/command.out" 2>"$WORK/command.err" || fail "${1##*/} failed"; }

# Check repository/key access before taking the API offline. Never auto-init it.
run restic snapshots --json
systemctl is-active --quiet "$SERVICE" || fail 'API was not active before backup'
PAUSED=yes
date -u +%s > "$SPINA_BACKUP_STATE/api-paused"
run systemctl stop "$SERVICE"
# systemctl stop waits for the service to exit; all API writers are quiescent.
# Other database/file writers must be excluded by the operator's configuration.
run pg_dump --no-password --format=custom --file "$WORK/database.dump"
[[ -s "$WORK/database.dump" ]] || fail 'empty database archive'
run pg_restore --list "$WORK/database.dump"
run tar --force-local -cpf "$WORK/private-evidence.tar" -C "$SPINA_BACKUP_PRIVATE_ROOT" .
run tar --force-local -cpf "$WORK/configuration.tar" -C "$SPINA_BACKUP_CONFIG_ROOT" .
if [[ -n "${SPINA_BACKUP_RELEASE_ROOT:-}" ]]; then
  run tar --force-local -rpf "$WORK/configuration.tar" -C "$SPINA_BACKUP_RELEASE_ROOT" runtime.env git-sha
fi
for name in SPINA_BACKUP_CADDY_FILE SPINA_BACKUP_UNIT_FILE; do
  if [[ -n "${!name:-}" ]]; then
    run tar --force-local -rpf "$WORK/configuration.tar" -C "$(dirname "${!name}")" "$(basename "${!name}")"
  fi
done
run systemctl start "$SERVICE"
run systemctl is-active --quiet "$SERVICE"
PAUSED=no
rm -- "$SPINA_BACKUP_STATE/api-paused"
cd "$WORK"
sha256sum database.dump private-evidence.tar configuration.tar > SHA256SUMS
# Relative names provide stable snapshot paths; tags/host scope retention.
run restic backup --json --host "$SPINA_BACKUP_HOST" --tag spina-operational-v1 \
  database.dump private-evidence.tar configuration.tar SHA256SUMS
cp command.out snapshot.json
# Check metadata after every upload. Full read/restore verification is separate.
run restic check
if [[ "${SPINA_BACKUP_RETENTION_ENABLED:-no}" == yes ]]; then
  run restic forget --host "$SPINA_BACKUP_HOST" --tag spina-operational-v1 \
    --group-by host,tags --keep-daily "$SPINA_BACKUP_KEEP_DAILY" \
    --keep-weekly "$SPINA_BACKUP_KEEP_WEEKLY" --keep-monthly "$SPINA_BACKUP_KEEP_MONTHLY" --prune
fi
date -u +%s > "$SPINA_BACKUP_STATE/last-success.new"
mv "$SPINA_BACKUP_STATE/last-success.new" "$SPINA_BACKUP_STATE/last-success"
cp snapshot.json "$SPINA_BACKUP_STATE/last-snapshot.json"
printf '%s\n' 'spina backup completed; encrypted snapshot metadata checked'
