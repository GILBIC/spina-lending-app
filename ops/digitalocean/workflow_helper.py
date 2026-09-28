from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

HOST_PATTERN = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
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
    aliases = target.get("aliases")
    if (
        not isinstance(aliases, list)
        or not aliases
        or any(
            not isinstance(value, str) or not HOST_PATTERN.fullmatch(value)
            for value in aliases
        )
    ):
        raise ValueError("target aliases must declare valid production hostnames")
    domains = [hostname, *aliases]
    if len(set(domains)) != len(domains):
        raise ValueError("target domain declarations must not repeat")
    expected_hostname = f"spina.{host.replace('.', '-')}.sslip.io"
    if any(
        domain.endswith(".sslip.io") and domain != expected_hostname
        for domain in domains
    ):
        raise ValueError("fallback hostname does not match target host")
    origins = target.get("cors_origins")
    if (
        not isinstance(origins, list)
        or not origins
        or any(
            origin not in {f"https://{domain}" for domain in domains}
            for origin in origins
        )
    ):
        raise ValueError("CORS origins must be declared HTTPS domains")
    redirect = target.get("staff_invite_redirect_url", "")
    parsed = urlsplit(redirect)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in domains
        or parsed.port is not None
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("staff invite redirect must use a declared HTTPS domain")

    return {
        "run_id": run_id,
        "droplet_id": droplet_id,
        "host": host,
        "hostname": hostname,
        "aliases": aliases,
        "cors_origins": origins,
        "staff_invite_redirect_url": redirect,
    }


def write_private(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        os.chmod(path, 0o600)
        output.write(content)


def prepare_inputs(directory: Path) -> None:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    expected_workflow = (
        f"{repository}/.github/workflows/spina-digitalocean-deploy.yml@refs/heads/main"
    )
    if (
        os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REF_PROTECTED") != "true"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_WORKFLOW_REF") != expected_workflow
        or not re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", ""))
    ):
        raise ValueError("Deployment requires the trusted workflow on protected main")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("workflow run ID is invalid")
    target_value = os.environ.get("SPINA_DEPLOY_TARGET_JSON", "")
    secrets_value = os.environ.get("SPINA_RUNTIME_SECRETS_JSON", "")
    if not target_value or not secrets_value:
        raise ValueError("Protected production deployment inputs are missing")
    target = json.loads(target_value)
    secrets = json.loads(secrets_value)
    if not isinstance(target, dict) or not isinstance(secrets, dict):
        raise TypeError("Protected deployment inputs must be JSON objects")
    target["run_id"] = int(run_id)
    target_path = directory / "spina-target.json"
    secrets_path = directory / "spina-secrets.json"
    write_private(target_path, json.dumps(target))
    write_private(secrets_path, json.dumps(secrets))
    write_env(
        secrets_path=secrets_path,
        target_path=target_path,
        output_path=directory / "spina.env",
    )


def validate_caddy(*, target_path: Path, config_path: Path) -> None:
    target = load_target(target_path)
    domains = set()

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "host" and isinstance(child, list):
                    domains.update(child)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(load_json(config_path))
    if not {target["hostname"], *target["aliases"]}.issubset(domains):
        raise ValueError(
            "Candidate Caddy configuration is missing a declared production domain"
        )


def env_quote(value: str) -> str:
    return (
        '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    )


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
            raise ValueError(f"protected runtime input is missing {source}")
        if any(ord(character) < 32 for character in value):
            raise ValueError(f"protected runtime input {source} must be single-line")
        if source == "database_pooler_url":
            value = validate_session_pooler_url(value)
        values[destination] = value

    values.update(
        {
            "GILBIC_CORS_ORIGINS": ",".join(target["cors_origins"]),
            "GILBIC_STAFF_INVITE_REDIRECT_URL": target["staff_invite_redirect_url"],
            "GILBIC_GCASH_MODE": "disabled",
        }
    )
    write_private(
        output_path,
        "".join(f"{key}={env_quote(value)}\n" for key, value in values.items()),
    )


class DeclaredHttpsRedirects(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def __init__(self, domains: set[str]):
        super().__init__()
        self.domains = domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if (
            target.scheme != "https"
            or target.hostname not in self.domains
            or target.port not in (None, 443)
            or target.username is not None
            or target.password is not None
        ):
            raise ValueError(
                "Public verification redirect must stay on declared HTTPS hosts"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_public(*, target_path: Path, output_path: Path) -> None:
    # A failed retry cannot leave a previous success file behind.
    output_path.unlink(missing_ok=True)
    target = load_target(target_path)
    domains = [target["hostname"], *target["aliases"]]
    opener = build_opener(DeclaredHttpsRedirects(set(domains)))
    checks = {}
    for hostname in domains:
        responses = []
        for path in ("/health/live", "/health/ready", "/"):
            with opener.open(f"https://{hostname}{path}", timeout=15) as response:
                final = urlsplit(response.geturl())
                if (
                    response.status != 200
                    or final.scheme != "https"
                    or final.hostname not in domains
                ):
                    raise ValueError(
                        f"Public HTTPS verification failed for {hostname}{path}"
                    )
                data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ValueError(
                        "Public verification response exceeded the size limit"
                    )
                responses.append(data.decode("utf-8"))
        live, ready = json.loads(responses[0]), json.loads(responses[1])
        if (
            not isinstance(live, dict)
            or live.get("status") != "ok"
            or not isinstance(ready, dict)
            or ready.get("status") != "ready"
            or ready.get("database") != "ok"
            or "<title>Spina Lending Company</title>" not in responses[2]
            or 'id="login-form"' not in responses[2]
        ):
            raise ValueError(
                f"Public health or portal verification failed for {hostname}"
            )
        checks[hostname] = {
            "liveness": "ok",
            "readiness": "ready",
            "database": "ok",
            "portal": "ok",
        }
    output_path.write_text(
        json.dumps({"run_id": target["run_id"], "domains": checks}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_evidence(
    *,
    target_path: Path,
    output_path: Path,
    git_sha: str,
    verified_active_sha: str,
    public_checks_path: Path,
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", git_sha):
        raise ValueError("git_sha must be a full lowercase commit SHA")
    if verified_active_sha != git_sha:
        raise ValueError("verified active revision must match the requested Git SHA")
    target = load_target(target_path)
    checks = load_json(public_checks_path)
    expected_domains = {target["hostname"], *target["aliases"]}
    public_domains = checks.get("domains")
    if (
        checks.get("run_id") != target["run_id"]
        or not isinstance(public_domains, dict)
        or set(public_domains) != expected_domains
        or any(
            value
            != {
                "liveness": "ok",
                "readiness": "ready",
                "database": "ok",
                "portal": "ok",
            }
            for value in public_domains.values()
        )
    ):
        raise ValueError(
            "Deployment evidence requires every declared domain to pass current-run public checks"
        )
    payload = {
        "git_sha": git_sha,
        "active_revision_verified": True,
        "droplet_id": target["droplet_id"],
        "host": target["host"],
        "hostname": target["hostname"],
        "url": f"https://{target['hostname']}",
        "liveness": "ok",
        "readiness": "ready",
        "database": "ok",
        "domains": public_domains,
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

    inputs = commands.add_parser("prepare-inputs")
    inputs.add_argument("--directory", required=True, type=Path)
    caddy = commands.add_parser("validate-caddy")
    caddy.add_argument("--target", required=True, type=Path)
    caddy.add_argument("--config", required=True, type=Path)
    hostnames = commands.add_parser("hostnames")
    hostnames.add_argument("--target", required=True, type=Path)

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
    evidence.add_argument("--verified-active-sha", required=True)
    evidence.add_argument("--public-checks", required=True, type=Path)

    public = commands.add_parser("verify-public")
    public.add_argument("--target", required=True, type=Path)
    public.add_argument("--output", required=True, type=Path)

    comment = commands.add_parser("write-comment")
    comment.add_argument("--target", required=True, type=Path)
    comment.add_argument("--output", required=True, type=Path)
    comment.add_argument("--git-sha", required=True)
    return root


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "prepare-inputs":
        prepare_inputs(arguments.directory)
    elif arguments.command == "validate-caddy":
        validate_caddy(target_path=arguments.target, config_path=arguments.config)
    elif arguments.command == "hostnames":
        target = load_target(arguments.target)
        print(", ".join([target["hostname"], *target["aliases"]]))
    elif arguments.command == "validate-target":
        load_target(arguments.target, expected_run_id=arguments.expected_run_id)
    elif arguments.command == "write-env":
        write_env(
            secrets_path=arguments.secrets,
            target_path=arguments.target,
            output_path=arguments.output,
        )
    elif arguments.command == "verify-public":
        verify_public(target_path=arguments.target, output_path=arguments.output)
    elif arguments.command == "write-evidence":
        write_evidence(
            target_path=arguments.target,
            output_path=arguments.output,
            git_sha=arguments.git_sha,
            verified_active_sha=arguments.verified_active_sha,
            public_checks_path=arguments.public_checks,
        )
    elif arguments.command == "write-comment":
        write_comment(
            target_path=arguments.target,
            output_path=arguments.output,
            git_sha=arguments.git_sha,
        )


if __name__ == "__main__":
    main()
