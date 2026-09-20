#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf 'SPINA_DEPLOY_ERROR: %s\n' "$*" >&2
  exit 1
}

validate_staged_input() {
  local expected_sha="$1" directory="$2" expected_digest="$3" actual_digest source_sha
  [[ "$expected_sha" =~ ^[0-9a-f]{40}$ && "$expected_digest" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ -s "$directory/release.tar.gz" && -s "$directory/runtime.env" ]] || return 1
  actual_digest="$(sha256sum "$directory/release.tar.gz" | cut -d ' ' -f 1)" || return 1
  [[ "$actual_digest" == "$expected_digest" ]] || return 1
  source_sha="$(tar -xOf "$directory/release.tar.gz" spina-git-sha)" || return 1
  [[ "$source_sha" == "$expected_sha" ]]
}

verify_release_paths() {
  local expected_sha="$1" current="$2" portal="$3" process_cwd="$4" release
  [[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || return 1
  release="$(readlink -f -- "$current")" || return 1
  [[ -f "$release/git-sha" && "$(cat "$release/git-sha")" == "$expected_sha" ]] || return 1
  [[ "$(readlink -f -- "$portal")" == "$release/dist" ]] || return 1
  [[ "$(readlink -f -- "$process_cwd")" == "$release" ]]
}

verify_active_revision() {
  local expected_sha="$1" pid
  pid="$(systemctl show --property MainPID --value spina-api)" || return 1
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  verify_release_paths "$expected_sha" /opt/spina/current /var/www/spina "/proc/$pid/cwd"
}

preserve_operator_environment() {
  local legacy="$1" operator="$2" line keep=true
  # Generated settings are single-line systemd assignments. Preserve every other
  # operator assignment (including continuation lines) without evaluating it.
  if [[ ! -e "$operator" ]]; then
    (umask 077; : > "$operator")
    if [[ -f "$legacy" ]]; then
      while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)= ]]; then
          keep=true
          case "${BASH_REMATCH[1]}" in
            GILBIC_APP_NAME|GILBIC_ENVIRONMENT|GILBIC_DATABASE_URL|GILBIC_SUPABASE_URL|GILBIC_SUPABASE_PUBLISHABLE_KEY|GILBIC_SUPABASE_SECRET_KEY|GILBIC_CORS_ORIGINS|GILBIC_STAFF_INVITE_REDIRECT_URL|GILBIC_GCASH_MODE)
              keep=false ;;
          esac
        fi
        if [[ "$keep" == true ]]; then printf '%s\n' "$line" >> "$operator"; fi
      done < "$legacy"
    fi
  fi
  chmod 600 "$operator"
}

snapshot_deployment() {
  local backup="$1" path index=0
  shift
  for path in "$@"; do
    index=$((index + 1))
    if [[ -e "$path" || -L "$path" ]]; then
      [[ ! -d "$path" || -L "$path" ]] || fail "deployment target is not a file or link"
      cp -a -- "$path" "$backup/$index"
    fi
  done
}

activate_deployment() {
  local release="$1" current="$2" portal="$3" unit="$4" caddy="$5"
  install -m 0644 "$release/spina-api.service" "$unit"
  install -m 0644 "$release/Caddyfile" "$caddy"
  ln -sfn -T "$release" "$current"
  ln -sfn -T "$release/dist" "$portal"
  systemctl daemon-reload
  systemctl enable --now spina-api
  systemctl enable --now caddy
  systemctl restart spina-api
  systemctl reload caddy
}

rollback_deployment() {
  local backup="$1" path index=0 failed=0
  shift
  # Continue restoring independent files if a service command fails. Any failed
  # recovery is reported instead of presenting the candidate as successful.
  systemctl stop spina-api || failed=1
  for path in "$@"; do
    index=$((index + 1))
    rm -f -- "$path" || { failed=1; continue; }
    if [[ -e "$backup/$index" || -L "$backup/$index" ]]; then
      cp -a -- "$backup/$index" "$path" || failed=1
    fi
  done
  systemctl daemon-reload || failed=1
  if [[ -e "$backup/3" ]]; then
    systemctl restart spina-api || failed=1
  else
    systemctl disable --now spina-api || failed=1
  fi
  if [[ -e "$backup/4" ]]; then
    systemctl reload caddy || failed=1
  else
    systemctl stop caddy || failed=1
  fi
  return "$failed"
}

deployment_exit() {
  local status=$?
  trap - EXIT
  if [[ "${ACTIVATION_STARTED:-false}" == true && "${ACTIVATED:-false}" != true ]]; then
    printf 'SPINA_DEPLOY_ROLLBACK: restoring previous runtime and configuration\n' >&2
    if ! rollback_deployment "$ACTIVATION_BACKUP" "${DEPLOYMENT_PATHS[@]}"; then
      printf 'SPINA_DEPLOY_ERROR: rollback needs operator recovery\n' >&2
    fi
    status=1
  fi
  if [[ -n "${RUN_DIR:-}" ]]; then
    rm -f -- "$RUN_DIR/runtime.env"
    printf '%s\n' "$status" > "$RUN_DIR/exit-code.tmp"
    mv -f -- "$RUN_DIR/exit-code.tmp" "$RUN_DIR/exit-code"
  fi
  exit "$status"
}

# End deployment lifecycle functions.

package_manager_busy() {
  local lock_path
  for lock_path in \
    /var/lib/dpkg/lock-frontend \
    /var/lib/dpkg/lock \
    /var/lib/apt/lists/lock \
    /var/cache/apt/archives/lock; do
    if command -v fuser >/dev/null 2>&1 && fuser "$lock_path" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

wait_for_package_manager() {
  local waited=0
  while package_manager_busy; do
    if (( waited >= 900 )); then
      fail "timed out waiting for active package-manager lock holders"
    fi
    if (( waited % 60 == 0 )); then
      printf 'SPINA_DEPLOY_WAIT: package manager is active (%ss)\n' "$waited"
    fi
    sleep 5
    waited=$((waited + 5))
  done
}

dpkg_repair() {
  local attempt
  for attempt in $(seq 1 60); do
    wait_for_package_manager
    if dpkg --configure -a; then
      return 0
    fi
    sleep 5
  done
  fail "dpkg repair did not complete"
}

wait_for_first_boot_packages() {
  if command -v cloud-init >/dev/null 2>&1; then
    timeout 900 cloud-init status --wait >/dev/null 2>&1 \
      || fail "cloud-init did not finish successfully"
  fi
  dpkg_repair
}

apt_retry() {
  local attempt
  local executable="$1"
  shift
  for attempt in 1 2 3 4 5 6; do
    wait_for_package_manager
    if [[ "$executable" == "apt-get" ]]; then
      if apt-get -o DPkg::Lock::Timeout=300 "$@"; then
        return 0
      fi
    elif "$executable" "$@"; then
      return 0
    fi
    if (( attempt == 6 )); then
      fail "package command failed after ${attempt} attempts: ${executable} $*"
    fi
    sleep $((attempt * 5))
  done
}

if [[ "${1:-}" == "--verify-active" ]]; then
  [[ $# -eq 2 ]] || fail "usage: bootstrap.sh --verify-active <git-sha>"
  verify_active_revision "$2" || fail "active runtime or portal revision does not match"
  printf '%s\n' "$2"
  exit 0
fi

[[ $# -eq 4 ]] || fail "usage: bootstrap.sh <git-sha> <hostname> <run-directory> <archive-sha256>"
SHA="$1"
HOSTNAME="$2"
RUN_DIR="$3"
ARCHIVE_SHA256="$4"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "invalid Git SHA"
[[ "$HOSTNAME" =~ ^spina\.[0-9]{1,3}(-[0-9]{1,3}){3}\.sslip\.io$ ]] || fail "invalid deployment hostname"
[[ "$RUN_DIR" =~ ^/var/lib/spina-deploy/run-[1-9][0-9]*-[1-9][0-9]*$ ]] || fail "invalid run directory"
[[ "$(readlink -f -- "$RUN_DIR")" == "$RUN_DIR" && -d "$RUN_DIR" ]] || fail "run directory must be a real private directory"
readonly SHA HOSTNAME RUN_DIR ARCHIVE_SHA256
ACTIVATION_STARTED=false
ACTIVATED=false
trap deployment_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
validate_staged_input "$SHA" "$RUN_DIR" "$ARCHIVE_SHA256" || fail "staged release identity or archive digest does not match"
install -d -m 0755 /opt/spina/releases
exec 9>/opt/spina/deployment.lock
flock -n 9 || fail "another deployment is already running"

export DEBIAN_FRONTEND=noninteractive
wait_for_first_boot_packages
apt_retry apt-get update -y
apt_retry apt-get install -y --no-install-recommends \
  apt-transport-https \
  ca-certificates \
  curl \
  debian-archive-keyring \
  debian-keyring \
  gnupg \
  python3 \
  python3-pip \
  python3-venv \
  ufw

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  > /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
chmod o+r /etc/apt/sources.list.d/caddy-stable.list
apt_retry apt-get update -y
apt_retry apt-get install -y --no-install-recommends caddy

if ! swapon --show --noheadings | grep -q .; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if ! id -u spina >/dev/null 2>&1; then
  useradd --system --home /var/lib/spina --create-home --shell /usr/sbin/nologin spina
fi

install -d -m 0755 /opt/spina/releases /etc/spina /var/www
install -d -m 0700 -o spina -g spina /var/lib/spina
preserve_operator_environment /etc/spina/spina.env /etc/spina/operator.env
chown root:root /etc/spina/operator.env

# A unique, final path avoids moving virtualenvs (their launchers embed paths)
# and never replaces a runtime still used by the current or previous release.
RELEASE_DIR="$(mktemp -d "/opt/spina/releases/${SHA}.XXXXXX")"
chmod 0755 "$RELEASE_DIR"
tar -xzf "$RUN_DIR/release.tar.gz" -C "$RELEASE_DIR"
[[ -f "$RELEASE_DIR/requirements.txt" ]] || fail "release is missing requirements.txt"
[[ -d "$RELEASE_DIR/gilbic_backend" ]] || fail "release is missing gilbic_backend"
[[ -d "$RELEASE_DIR/spina_backend_mobile" ]] || fail "release is missing spina_backend_mobile"
[[ -f "$RELEASE_DIR/dist/index.html" ]] || fail "release is missing portal build"
printf '%s\n' "$SHA" > "$RELEASE_DIR/git-sha"

python3 -m venv "$RELEASE_DIR/venv"
"$RELEASE_DIR/venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
"$RELEASE_DIR/venv/bin/python" -m pip install --disable-pip-version-check -r "$RELEASE_DIR/requirements.txt"
"$RELEASE_DIR/venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
  "$RELEASE_DIR/spina_backend_mobile" \
  "$RELEASE_DIR/gilbic_backend"

install -m 0600 -o root -g root "$RUN_DIR/runtime.env" "$RELEASE_DIR/runtime.env"
rm -f -- "$RUN_DIR/runtime.env" "$RUN_DIR/release.tar.gz"

cat > "$RELEASE_DIR/logging.json" <<'LOGGING'
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "default": {"()": "uvicorn.logging.DefaultFormatter", "fmt": "%(levelprefix)s %(message)s"},
    "request": {"format": "%(message)s"}
  },
  "handlers": {
    "default": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stderr"},
    "request": {"class": "logging.StreamHandler", "formatter": "request", "stream": "ext://sys.stdout"},
    "discard": {"class": "logging.NullHandler"}
  },
  "loggers": {
    "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": false},
    "uvicorn.error": {"level": "INFO"},
    "uvicorn.access": {"handlers": ["discard"], "level": "INFO", "propagate": false},
    "gilbic.request": {"handlers": ["request"], "level": "INFO", "propagate": false}
  }
}
LOGGING

cat > "$RELEASE_DIR/spina-api.service" <<'UNIT'
[Unit]
Description=Spina FastAPI service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=spina
Group=spina
WorkingDirectory=/opt/spina/current
EnvironmentFile=/opt/spina/current/runtime.env
EnvironmentFile=-/etc/spina/operator.env
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/opt/spina/current/venv/bin/python -m gilbic_backend.release_preflight --profile runtime
ExecStart=/opt/spina/current/venv/bin/python -m uvicorn gilbic_backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1 --no-access-log --log-config /opt/spina/current/logging.json
Restart=always
RestartSec=5
TimeoutStartSec=90
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
ReadWritePaths=/var/lib/spina
UMask=0027
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT

cat > "$RELEASE_DIR/Caddyfile" <<CADDY
{
  email gilbicsanjose@gmail.com
  servers :443 {
    protocols h1 h2
  }
}

$HOSTNAME {
  encode zstd gzip

  header {
    -Server
    X-Content-Type-Options "nosniff"
    Referrer-Policy "strict-origin-when-cross-origin"
    X-Frame-Options "DENY"
    Permissions-Policy "camera=(), microphone=(), geolocation=()"
    Strict-Transport-Security "max-age=31536000"
  }

  handle /api/* {
    reverse_proxy 127.0.0.1:8000
  }

  handle /health/* {
    reverse_proxy 127.0.0.1:8000
  }

  handle {
    root * /var/www/spina
    try_files {path} /index.html
    file_server
  }
}
CADDY

# Verify the candidate interpreter before activation; systemd validates syntax
# using an executable path that already exists rather than the old current link.
sed "s|/opt/spina/current|$RELEASE_DIR|g" \
  "$RELEASE_DIR/spina-api.service" > "$RELEASE_DIR/spina-api-verify.service"
systemd-analyze verify "$RELEASE_DIR/spina-api-verify.service"
caddy validate --config "$RELEASE_DIR/Caddyfile" --adapter caddyfile

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

ACTIVATION_BACKUP="$(mktemp -d /opt/spina/releases/.activation.XXXXXX)"
DEPLOYMENT_PATHS=(/opt/spina/current /var/www/spina /etc/systemd/system/spina-api.service /etc/caddy/Caddyfile)
snapshot_deployment "$ACTIVATION_BACKUP" "${DEPLOYMENT_PATHS[@]}"
ACTIVATION_STARTED=true
activate_deployment "$RELEASE_DIR" "${DEPLOYMENT_PATHS[@]}"

for _ in $(seq 1 60); do
  if curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/health/live >"$RUN_DIR/live.json" \
    && curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/health/ready >"$RUN_DIR/ready.json" \
    && grep -Eq '"database"[[:space:]]*:[[:space:]]*"ok"' "$RUN_DIR/ready.json" \
    && verify_active_revision "$SHA"; then
    ACTIVATED=true
    printf 'SPINA_DEPLOY_OK sha=%s host=%s\n' "$SHA" "$HOSTNAME"
    exit 0
  fi
  sleep 2
done

systemctl --no-pager --full status spina-api >&2 || true
journalctl -u spina-api --no-pager -n 100 >&2 || true
fail "local health checks did not become ready"
