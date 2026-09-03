from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "digitalocean" / "bootstrap.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "spina-digitalocean-deploy.yml"
HELPER = ROOT / "ops" / "digitalocean" / "workflow_helper.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_helper(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def verify_helper_contract() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        target_path = directory / "target.json"
        target_path.write_text(
            json.dumps(
                {
                    "run_id": 12345,
                    "droplet_id": 67890,
                    "host": "159.223.39.43",
                    "hostname": "spina.159-223-39-43.sslip.io",
                }
            ),
            encoding="utf-8",
        )
        valid = run_helper(
            "validate-target",
            "--target",
            str(target_path),
            "--expected-run-id",
            "12345",
        )
        require(valid.returncode == 0, valid.stderr or "valid target was rejected")

        stale = run_helper(
            "validate-target",
            "--target",
            str(target_path),
            "--expected-run-id",
            "54321",
        )
        require(stale.returncode != 0, "stale target run ID must be rejected")

        secret_path = directory / "secrets.json"
        secret_path.write_text(
            json.dumps(
                {
                    "database_url": "postgresql://runtime:secret@db.example/postgres",
                    "database_pooler_url": "postgresql://runtime:secret@pooler.example:5432/postgres?sslmode=require",
                    "supabase_url": "https://project.example",
                    "supabase_publishable_key": "publishable-test",
                    "supabase_secret_key": "secret-test",
                }
            ),
            encoding="utf-8",
        )
        env_path = directory / "spina.env"
        written = run_helper(
            "write-env",
            "--secrets",
            str(secret_path),
            "--target",
            str(target_path),
            "--output",
            str(env_path),
        )
        require(written.returncode == 0, written.stderr or "environment writer failed")
        env_text = env_path.read_text(encoding="utf-8")
        require(
            'GILBIC_DATABASE_URL="postgresql://runtime:secret@pooler.example:5432/postgres?sslmode=require"'
            in env_text,
            "DigitalOcean runtime must use the IPv4 session pooler URL",
        )
        require("db.example" not in env_text, "direct IPv6 database URL must not reach the Droplet")
        require(
            'GILBIC_CORS_ORIGINS="https://spina.159-223-39-43.sslip.io"' in env_text,
            "public HTTPS origin is missing",
        )
        require(env_path.stat().st_mode & 0o777 == 0o600, "environment file must be 0600")


def main() -> None:
    require(BOOTSTRAP.is_file(), f"missing {BOOTSTRAP.relative_to(ROOT)}")
    require(WORKFLOW.is_file(), f"missing {WORKFLOW.relative_to(ROOT)}")
    require(HELPER.is_file(), f"missing {HELPER.relative_to(ROOT)}")

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    require("set -Eeuo pipefail" in bootstrap, "bootstrap must fail closed")
    require("127.0.0.1:8000" in bootstrap, "Uvicorn must remain loopback-only")
    require("caddy validate" in bootstrap, "Caddy configuration must be validated")
    require("systemd-analyze verify" in bootstrap, "systemd unit must be verified")
    require("chmod 600 /etc/spina/spina.env" in bootstrap, "runtime environment must be root-only")
    require("ufw --force enable" in bootstrap, "host firewall must be enabled")
    require("dl.cloudsmith.io/public/caddy/stable" in bootstrap, "official Caddy package repository is required")

    require("wait_for_first_boot_packages" in bootstrap, "bootstrap must coordinate with Ubuntu first boot")
    require("cloud-init status --wait" in bootstrap, "bootstrap must wait for cloud-init")
    for lock_path in (
        "/var/lib/dpkg/lock-frontend",
        "/var/lib/dpkg/lock",
        "/var/lib/apt/lists/lock",
        "/var/cache/apt/archives/lock",
    ):
        require(lock_path in bootstrap, f"bootstrap must wait for {lock_path}")
    require("apt_retry apt-get update" in bootstrap, "apt update must use bounded retry")
    require("apt_retry apt-get install" in bootstrap, "apt install must use bounded retry")
    require("dpkg --configure -a" in bootstrap, "interrupted package state must be repaired")

    require("id-token: write" in workflow, "workflow must request GitHub OIDC")
    require("https://$HOSTNAME/health/live" in workflow, "public liveness must use HTTPS")
    require("https://$HOSTNAME/health/ready" in workflow, "public readiness must use HTTPS")
    require("database == \"ok\"" in workflow, "database readiness must be asserted")
    require("ssh-keygen -t ed25519" in workflow, "deployment key must be ephemeral")
    require("digitalocean-public-key.txt" in workflow, "public-key rendezvous is required")
    require("digitalocean-target.json" in workflow, "target rendezvous is required")
    require('if encoded_target="$(gh api' in workflow, "missing rendezvous must be handled by command status")
    require(
        'digitalocean-target.json?ref=${GITHUB_REF_NAME}" --jq .content 2>/dev/null || true' not in workflow,
        "missing rendezvous must not be decoded as base64",
    )
    require("trap 'rm -f" in workflow, "temporary secret files must be deleted")
    require("<<" not in workflow, "workflow must not use indentation-sensitive heredocs")
    require("SUPABASE_DB_URL" not in workflow, "workflow must not name or embed the database secret")
    require("SUPABASE_SERVICE_ROLE_KEY" not in workflow, "workflow must not name or embed the admin secret")
    require("private_key" not in workflow.lower(), "workflow must not embed a private key")

    require(
        "spina-digitalocean-run-${GITHUB_RUN_ID}" in workflow,
        "workflow key cleanup must target the exact run comment",
    )
    require("/root/.ssh/authorized_keys" in workflow, "workflow must clean the server authorized_keys file")
    require("grep -vF" in workflow, "workflow must remove only the exact short-lived key comment")

    require("start_remote_bootstrap" in workflow, "bootstrap must start through a recoverable helper")
    require("nohup bash /tmp/spina-bootstrap.sh" in workflow, "bootstrap must survive an SSH disconnect")
    require("/var/lib/spina-bootstrap.exit" in workflow, "bootstrap must persist its exit status")
    require("/var/log/spina-bootstrap.log" in workflow, "bootstrap must persist a diagnostic log")
    require("poll_remote_bootstrap" in workflow, "workflow must reconnect and poll bootstrap completion")
    require("ServerAliveInterval=15" in workflow, "SSH sessions must send keepalives")
    require("ServerAliveCountMax=4" in workflow, "SSH keepalive failure must be bounded")
    require("ConnectionAttempts=3" in workflow, "SSH connection establishment must retry")

    verify_helper_contract()
    print("DigitalOcean deployment contract passed.")


if __name__ == "__main__":
    main()
