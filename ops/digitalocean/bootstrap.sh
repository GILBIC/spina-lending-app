#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf 'SPINA_DEPLOY_ERROR: %s\n' "$*" >&2
  exit 1
}

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

[[ $# -eq 2 ]] || fail "usage: bootstrap.sh <git-sha> <hostname>"
SHA="$1"
HOSTNAME="$2"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "invalid Git SHA"
[[ "$HOSTNAME" =~ ^spina\.[0-9]{1,3}(-[0-9]{1,3}){3}\.sslip\.io$ ]] || fail "invalid deployment hostname"
[[ -s /tmp/spina-release.tar.gz ]] || fail "missing release archive"
[[ -s /tmp/spina.env ]] || fail "missing runtime environment"

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

install -d -m 0755 /opt/spina/releases /etc/spina /var/www /var/lib/spina
RELEASE_DIR="/opt/spina/releases/$SHA"
STAGING_DIR="${RELEASE_DIR}.staging"
rm -rf "$STAGING_DIR"
install -d -m 0755 "$STAGING_DIR"
tar -xzf /tmp/spina-release.tar.gz -C "$STAGING_DIR"
[[ -f "$STAGING_DIR/requirements.txt" ]] || fail "release is missing requirements.txt"
[[ -d "$STAGING_DIR/gilbic_backend" ]] || fail "release is missing gilbic_backend"
[[ -d "$STAGING_DIR/spina_backend_mobile" ]] || fail "release is missing spina_backend_mobile"
[[ -f "$STAGING_DIR/dist/index.html" ]] || fail "release is missing portal build"

if [[ ! -x /opt/spina/venv/bin/python ]]; then
  python3 -m venv /opt/spina/venv
fi
/opt/spina/venv/bin/python -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
/opt/spina/venv/bin/python -m pip install --disable-pip-version-check -r "$STAGING_DIR/requirements.txt"
/opt/spina/venv/bin/python -m pip install --disable-pip-version-check --force-reinstall --no-deps \
  "$STAGING_DIR/spina_backend_mobile" \
  "$STAGING_DIR/gilbic_backend"

rm -rf "$RELEASE_DIR"
mv "$STAGING_DIR" "$RELEASE_DIR"
ln -sfn "$RELEASE_DIR" /opt/spina/current
ln -sfn "$RELEASE_DIR/dist" /var/www/spina

install -m 0600 -o root -g root /tmp/spina.env /etc/spina/spina.env
chmod 600 /etc/spina/spina.env
rm -f /tmp/spina.env /tmp/spina-release.tar.gz

cat > /etc/systemd/system/spina-api.service <<'UNIT'
[Unit]
Description=Spina FastAPI service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=spina
Group=spina
WorkingDirectory=/opt/spina/current
EnvironmentFile=/etc/spina/spina.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/spina/venv/bin/uvicorn gilbic_backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
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

cat > /etc/caddy/Caddyfile <<CADDY
{
  email gilbicsanjose@gmail.com
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

systemd-analyze verify /etc/systemd/system/spina-api.service
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable --now spina-api
systemctl enable --now caddy
systemctl restart spina-api
systemctl reload caddy

for _ in $(seq 1 60); do
  if curl --fail --silent --show-error http://127.0.0.1:8000/health/live >/tmp/spina-live.json \
    && curl --fail --silent --show-error http://127.0.0.1:8000/health/ready >/tmp/spina-ready.json \
    && grep -Eq '"database"[[:space:]]*:[[:space:]]*"ok"' /tmp/spina-ready.json; then
    printf 'SPINA_DEPLOY_OK sha=%s host=%s\n' "$SHA" "$HOSTNAME"
    exit 0
  fi
  sleep 2
done

systemctl --no-pager --full status spina-api >&2 || true
journalctl -u spina-api --no-pager -n 100 >&2 || true
fail "local health checks did not become ready"
