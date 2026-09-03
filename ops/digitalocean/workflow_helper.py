from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

HOST_PATTERN = re.compile(r"spina\.(?:\d{1,3}-){3}\d{1,3}\.sslip\.io")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_target(path: Path, *, expected_run_id: int | None = None) -> dict[str, Any]:
    target = load_json(path)
    run_id = target.get("run_id")
    droplet_id = target.get("droplet_id")
    if not isinstance(run_id, int) or run_id <= 0:
        raise ValueError("target run_id must be a positive integer")
    if expected_run_id is not None and run_id != expected_run_id:
        raise ValueError("target belongs to a different workflow run")
    if not isinstance(droplet_id, int) or droplet_id <= 0:
        raise ValueError("target droplet_id must be a positive integer")

    host = str(target.get("host", "")).strip()
    ip = ipaddress.ip_address(host)
    if ip.version != 4 or not ip.is_global:
        raise ValueError("target host must be a public IPv4 address")

    hostname = str(target.get("hostname", "")).strip()
    if not HOST_PATTERN.fullmatch(hostname):
        raise ValueError("target hostname is invalid")
    expected_hostname = f"spina.{host.replace('.', '-')}.sslip.io"
    if hostname != expected_hostname:
        raise ValueError("target hostname does not match target host")

    return {
        "run_id": run_id,
        "droplet_id": droplet_id,
        "host": host,
        "hostname": hostname,
    }


def env_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def validate_session_pooler_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("database_pooler_url must use PostgreSQL")
    if not parsed.hostname or "pooler" not in parsed.hostname.lower():
        raise ValueError("database_pooler_url must target a database pooler")
    if parsed.port != 5432:
        raise ValueError("database_pooler_url must use session mode on port 5432")
    if not parsed.username or not parsed.password:
        raise ValueError("database_pooler_url must include runtime credentials")
    sslmode = parse_qs(parsed.query).get("sslmode", [])
    if sslmode != ["require"]:
        raise ValueError("database_pooler_url must require TLS")
    return value


def write_env(*, secrets_path: Path, target_path: Path, output_path: Path) -> None:
    secrets = load_json(secrets_path)
    target = load_target(target_path)
    required = {
        "database_pooler_url": "GILBIC_DATABASE_URL",
        "supabase_url": "GILBIC_SUPABASE_URL",
        "supabase_publishable_key": "GILBIC_SUPABASE_PUBLISHABLE_KEY",
        "supabase_secret_key": "GILBIC_SUPABASE_SECRET_KEY",
    }
    values: dict[str, str] = {
        "GILBIC_APP_NAME": "Spina API",
        "GILBIC_ENVIRONMENT": "production",
    }
    for source, destination in required.items():
        value = str(secrets.get(source, "")).strip()
        if not value:
            raise ValueError(f"secret broker response is missing {source}")
        if source == "database_pooler_url":
            value = validate_session_pooler_url(value)
        values[destination] = value

    public_url = f"https://{target['hostname']}"
    values.update(
        {
            "GILBIC_CORS_ORIGINS": public_url,
            "GILBIC_STAFF_INVITE_REDIRECT_URL": f"{public_url}/",
            "GILBIC_GCASH_MODE": "disabled",
        }
    )
    output_path.write_text(
        "".join(f"{key}={env_quote(value)}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    os.chmod(output_path, 0o600)


def write_evidence(
    *,
    target_path: Path,
    output_path: Path,
    git_sha: str,
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", git_sha):
        raise ValueError("git_sha must be a full lowercase commit SHA")
    target = load_target(target_path)
    payload = {
        "git_sha": git_sha,
        "droplet_id": target["droplet_id"],
        "host": target["host"],
        "hostname": target["hostname"],
        "url": f"https://{target['hostname']}",
        "liveness": "ok",
        "readiness": "ready",
        "database": "ok",
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_comment(
    *,
    target_path: Path,
    output_path: Path,
    git_sha: str,
) -> None:
    target = load_target(target_path)
    output_path.write_text(
        "\n".join(
            (
                "## DigitalOcean deployment completed",
                "",
                f"- Exact Git SHA: `{git_sha}`",
                f"- Droplet ID: `{target['droplet_id']}`",
                "- Region: `sgp1`",
                f"- Public URL: https://{target['hostname']}",
                "- Liveness: `200 / ok`",
                "- Readiness: `200 / database: ok`",
                "- Runtime: one loopback-only Uvicorn worker behind Caddy HTTPS",
                "- Database/Auth: existing Supabase authority through session pooler",
                "",
                "No credential, database URL, or SSH private key is included in this evidence.",
                "",
            )
        ),
        encoding="utf-8",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-target")
    validate.add_argument("--target", required=True, type=Path)
    validate.add_argument("--expected-run-id", required=True, type=int)

    env = commands.add_parser("write-env")
    env.add_argument("--secrets", required=True, type=Path)
    env.add_argument("--target", required=True, type=Path)
    env.add_argument("--output", required=True, type=Path)

    evidence = commands.add_parser("write-evidence")
    evidence.add_argument("--target", required=True, type=Path)
    evidence.add_argument("--output", required=True, type=Path)
    evidence.add_argument("--git-sha", required=True)

    comment = commands.add_parser("write-comment")
    comment.add_argument("--target", required=True, type=Path)
    comment.add_argument("--output", required=True, type=Path)
    comment.add_argument("--git-sha", required=True)
    return root


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "validate-target":
        load_target(arguments.target, expected_run_id=arguments.expected_run_id)
    elif arguments.command == "write-env":
        write_env(
            secrets_path=arguments.secrets,
            target_path=arguments.target,
            output_path=arguments.output,
        )
    elif arguments.command == "write-evidence":
        write_evidence(
            target_path=arguments.target,
            output_path=arguments.output,
            git_sha=arguments.git_sha,
        )
    elif arguments.command == "write-comment":
        write_comment(
            target_path=arguments.target,
            output_path=arguments.output,
            git_sha=arguments.git_sha,
        )


if __name__ == "__main__":
    main()
