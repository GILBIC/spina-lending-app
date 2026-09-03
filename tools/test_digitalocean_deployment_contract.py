from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "digitalocean" / "bootstrap.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "spina-digitalocean-deploy.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(BOOTSTRAP.is_file(), f"missing {BOOTSTRAP.relative_to(ROOT)}")
    require(WORKFLOW.is_file(), f"missing {WORKFLOW.relative_to(ROOT)}")

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    require("set -Eeuo pipefail" in bootstrap, "bootstrap must fail closed")
    require("127.0.0.1:8000" in bootstrap, "Uvicorn must remain loopback-only")
    require("caddy validate" in bootstrap, "Caddy configuration must be validated")
    require("systemd-analyze verify" in bootstrap, "systemd unit must be verified")
    require("chmod 600 /etc/spina/spina.env" in bootstrap, "runtime environment must be root-only")
    require("ufw --force enable" in bootstrap, "host firewall must be enabled")

    require("id-token: write" in workflow, "workflow must request GitHub OIDC")
    require("https://$HOSTNAME/health/live" in workflow, "public liveness must use HTTPS")
    require("https://$HOSTNAME/health/ready" in workflow, "public readiness must use HTTPS")
    require("database: ok" in workflow, "database readiness must be asserted")
    require("ssh-keygen -t ed25519" in workflow, "deployment key must be ephemeral")
    require("digitalocean-public-key.txt" in workflow, "public-key rendezvous is required")
    require("digitalocean-target.json" in workflow, "target rendezvous is required")
    require("trap 'rm -f" in workflow, "temporary secret files must be deleted")
    require("SUPABASE_DB_URL" not in workflow, "workflow must not name or embed the database secret")
    require("SUPABASE_SERVICE_ROLE_KEY" not in workflow, "workflow must not name or embed the admin secret")
    require("private_key" not in workflow.lower(), "workflow must not embed a private key")

    print("DigitalOcean deployment contract passed.")


if __name__ == "__main__":
    main()
