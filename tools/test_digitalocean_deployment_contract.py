from __future__ import annotations

import json
import os
import re
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
                    "hostname": "spina.com.ph",
                    "aliases": [
                        "app.spina.com.ph",
                        "api.spina.com.ph",
                        "www.spina.com.ph",
                        "spina.159-223-39-43.sslip.io",
                    ],
                    "cors_origins": [
                        "https://spina.com.ph",
                        "https://app.spina.com.ph",
                    ],
                    "staff_invite_redirect_url": "https://app.spina.com.ph/",
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
        require(
            "db.example" not in env_text,
            "direct IPv6 database URL must not reach the Droplet",
        )
        require(
            'GILBIC_CORS_ORIGINS="https://spina.com.ph,https://app.spina.com.ph"'
            in env_text,
            "public HTTPS origin is missing",
        )
        # Windows chmod does not express POSIX owner-only permissions. Production
        # and Linux CI must enforce the real 0600 boundary.
        if os.name == "posix":
            require(
                env_path.stat().st_mode & 0o777 == 0o600,
                "environment file must be 0600",
            )
        evidence_path = directory / "evidence.json"
        checks_path = directory / "public-checks.json"
        target = json.loads(target_path.read_text(encoding="utf-8"))
        checks_path.write_text(
            json.dumps(
                {
                    "run_id": target["run_id"],
                    "domains": {
                        host: {
                            "liveness": "ok",
                            "readiness": "ready",
                            "database": "ok",
                            "portal": "ok",
                        }
                        for host in [target["hostname"], *target["aliases"]]
                    },
                }
            ),
            encoding="utf-8",
        )
        requested_sha = "a" * 40
        for active_sha, expected_success in (("b" * 40, False), (requested_sha, True)):
            evidence = run_helper(
                "write-evidence",
                "--target",
                str(target_path),
                "--output",
                str(evidence_path),
                "--git-sha",
                requested_sha,
                "--verified-active-sha",
                active_sha,
                "--public-checks",
                str(checks_path),
            )
            require(
                (evidence.returncode == 0) == expected_success,
                "deployment evidence must reject a different active revision",
            )
            require(
                evidence_path.exists() == expected_success,
                "failed identity checks must not publish evidence",
            )
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        require(
            payload["active_revision_verified"] is True,
            "active revision proof must be recorded",
        )


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
    require(
        'install -m 0600 -o root -g root "$RUN_DIR/runtime.env" "$RELEASE_DIR/runtime.env"'
        in bootstrap,
        "release runtime environment must be root-only",
    )
    require(
        "EnvironmentFile=-/etc/spina/operator.env" in bootstrap,
        "operator settings must survive redeployment",
    )
    require(
        "/opt/spina/venv" not in bootstrap,
        "release rollback must also restore Python packages",
    )
    require(
        "trap deployment_exit EXIT" in bootstrap,
        "failed activation must restore prior files and services",
    )
    require("ufw --force enable" in bootstrap, "host firewall must be enabled")
    require(
        "dl.cloudsmith.io/public/caddy/stable" in bootstrap,
        "official Caddy package repository is required",
    )

    caddy_h1_h2_only = re.search(
        r"^\s*protocols\s+h1\s+h2\s*$", bootstrap, re.MULTILINE
    )
    udp_443_open = "ufw allow 443/udp" in bootstrap
    require(
        bool(caddy_h1_h2_only) or udp_443_open,
        "Caddy HTTP/3 must not be advertised through a TCP-only firewall",
    )

    require(
        "wait_for_first_boot_packages" in bootstrap,
        "bootstrap must coordinate with Ubuntu first boot",
    )
    require(
        "cloud-init status --wait" in bootstrap, "bootstrap must wait for cloud-init"
    )
    for lock_path in (
        "/var/lib/dpkg/lock-frontend",
        "/var/lib/dpkg/lock",
        "/var/lib/apt/lists/lock",
        "/var/cache/apt/archives/lock",
    ):
        require(lock_path in bootstrap, f"bootstrap must wait for {lock_path}")
    require(
        "apt_retry apt-get update" in bootstrap, "apt update must use bounded retry"
    )
    require(
        "apt_retry apt-get install" in bootstrap, "apt install must use bounded retry"
    )
    require(
        "dpkg --configure -a" in bootstrap, "interrupted package state must be repaired"
    )

    require(
        "contents: read" in workflow and "contents: write" not in workflow,
        "deployment must not write protected source branches",
    )
    require(
        "environment: Production" in workflow,
        "deployment credentials must use the protected production environment",
    )
    require(
        "github.ref == 'refs/heads/main' && github.ref_protected == true" in workflow,
        "deployment must reject non-protected source",
    )
    require(
        "prepare-inputs --directory /tmp" in workflow,
        "trusted workflow context and production inputs must be validated",
    )
    require(
        "workflow_helper.py verify-public" in workflow,
        "public verification must cover declared domains",
    )
    require(
        "--public-checks /tmp/spina-public-checks.json" in workflow,
        "evidence must require completed domain verification",
    )
    require(
        "SPINA_DEPLOY_SSH_KEY" in workflow,
        "deployment requires an environment-owned SSH credential",
    )
    require(
        "SPINA_DEPLOY_KNOWN_HOSTS" in workflow,
        "deployment requires an independently verified host pin",
    )
    require(
        "ssh-keyscan" not in workflow, "network scans must never establish host trust"
    )
    require(
        'ssh-keygen -F "$HOST" -f /tmp/spina-known-hosts' in workflow,
        "host pin must cover the declared target before upload",
    )
    require(
        "StrictHostKeyChecking=yes" in workflow,
        "SSH must reject an identity that differs from the pin",
    )
    require(
        "SECRET_BROKER_URL" not in workflow and "put_branch_file" not in workflow,
        "deployment must not rely on the unavailable broker or branch rendezvous",
    )
    require("trap 'rm -f" in workflow, "temporary secret files must be deleted")
    require(
        "<<" not in workflow, "workflow must not use indentation-sensitive heredocs"
    )
    require(
        "SUPABASE_DB_URL" not in workflow,
        "workflow must not name or embed the database secret",
    )
    require(
        "SUPABASE_SERVICE_ROLE_KEY" not in workflow,
        "workflow must not name or embed the admin secret",
    )
    require(
        "private_key" not in workflow.lower(), "workflow must not embed a private key"
    )

    require(
        "authorized_keys" not in workflow,
        "redeployment must not remove a managed deployment or recovery key",
    )
    require(
        "--require-hashes --only-binary=:all:" in bootstrap
        and "--no-build-isolation" in bootstrap,
        "runtime and build dependencies must use the verified lock",
    )
    require(
        "requirements-runtime.lock" in workflow,
        "immutable release archive must include the runtime lock",
    )

    require(
        "start_remote_bootstrap" in workflow,
        "bootstrap must start through a recoverable helper",
    )
    require(
        "nohup bash '$REMOTE_RUN_DIR/bootstrap.sh'" in workflow,
        "bootstrap must survive an SSH disconnect",
    )
    require(
        "$REMOTE_RUN_DIR/exit-code" in workflow,
        "bootstrap must persist its exit status",
    )
    require(
        "$REMOTE_RUN_DIR/bootstrap.log" in workflow,
        "bootstrap must persist a diagnostic log",
    )
    require(
        "poll_remote_bootstrap" in workflow,
        "workflow must reconnect and poll bootstrap completion",
    )
    require("ServerAliveInterval=15" in workflow, "SSH sessions must send keepalives")
    require(
        "ServerAliveCountMax=4" in workflow, "SSH keepalive failure must be bounded"
    )
    require(
        "ConnectionAttempts=3" in workflow, "SSH connection establishment must retry"
    )

    verify_helper_contract()
    print("DigitalOcean deployment contract passed.")


if __name__ == "__main__":
    main()
