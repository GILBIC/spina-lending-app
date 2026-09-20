"""Read-only deployment checks; successful configuration is not go-live approval."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from ipaddress import ip_address
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict

from .config import Settings, get_settings
from .database import normalize_database_url_for_psycopg
from .employee_authorization import configured_employee_owner_id

REQUIRED_TABLES = (
    "core.users",
    "core.devices",
    "core.user_roles",
    "lending.clients",
    "lending.loans",
    "lending.client_payment_proofs",
    "core.employee_profiles",
    "core.employee_profile_versions",
    "core.employee_action_receipts",
    "core.employee_history",
)


class PreflightReport(TypedDict):
    kind: str
    status: str
    checks: dict[str, bool]
    activation_proven: bool


def _connect(settings: Settings):
    # Libpq startup options enforce read-only before any application query runs.
    return psycopg.connect(
        normalize_database_url_for_psycopg(settings.database_url),
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=5000",
        application_name="spina-release-preflight",
    )


def probe_database(settings: Settings) -> dict[str, bool]:
    checks = {"schema": False, "private_grants": False}
    try:
        with _connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT bool_and(to_regclass(name) IS NOT NULL) "
                "FROM unnest(%s::text[]) AS names(name)",
                (list(REQUIRED_TABLES),),
            )
            row = cursor.fetchone()
            checks["schema"] = bool(row and row[0])
            cursor.execute(
                """SELECT NOT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a
                    LEFT JOIN pg_roles r ON r.oid=a.grantee
                    WHERE n.nspname IN ('core','lending','accounting')
                    AND c.relkind IN ('r','p','v','m','f')
                    AND (a.grantee=0 OR r.rolname IN ('anon','authenticated'))
                    )"""
            )
            row = cursor.fetchone()
            checks["private_grants"] = bool(row and row[0])
    except (psycopg.Error, ValueError):
        # Driver errors may contain credentials, addresses or SQL; never serialize them.
        pass
    return checks


def _canonical_host(hostname: str) -> str | None:
    # Use ASCII/punycode host configuration and reject scoped/encoded IP forms.
    if not hostname.isascii() or "%" in hostname:
        return None
    try:
        address = ip_address(hostname)
    except ValueError:
        labels = hostname.removesuffix(".").split(".")
        if len(hostname) > 253 or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
            for label in labels
        ):
            return None
        # Browsers interpret numeric/hex final labels as IPv4, not DNS names.
        # Require ordinary IPv4 syntax accepted above instead of ambiguous forms.
        if re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)", labels[-1]):
            return None
        try:
            hostname.encode("ascii").decode("idna")
        except UnicodeError:
            return None
        return hostname
    return f"[{address.compressed}]" if address.version == 6 else str(address)


def _https_origin(value: str, *, exact_origin: bool = True) -> bool:
    try:
        if any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in value
        ):
            return False
        parsed = urlsplit(value)
        port = parsed.port  # Access explicitly: urlsplit alone accepts invalid ports.
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or port == 0
            or "@" in parsed.netloc
            or parsed.netloc.endswith(":")
            or "?" in value
            or "#" in value
            or parsed.path not in ({""} if exact_origin else {"", "/"})
        ):
            return False
        host = _canonical_host(parsed.hostname)
        if host is None:
            return False
        origin = "https://" + host + (f":{port}" if port not in {None, 443} else "")
        # CORS middleware compares literal strings. Match browser serialization,
        # including lowercase DNS, compressed IPv6 and omitted default ports.
        return not exact_origin or value == origin
    except ValueError:
        return False


def _report(kind: str, checks: dict[str, bool]) -> PreflightReport:
    return {
        "kind": kind,
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "activation_proven": False,
    }


def check_runtime(settings: Settings) -> PreflightReport:
    try:
        params = conninfo_to_dict(
            normalize_database_url_for_psycopg(settings.database_url)
        )
        tls = params.get("sslmode") in {"require", "verify-ca", "verify-full"}
        explicit_database = bool(
            params.get("host") and params.get("dbname") and params.get("user")
        )
    except (psycopg.Error, ValueError):
        tls = explicit_database = False
    checks = {
        "production_environment": settings.environment == "production",
        "database_tls": tls and explicit_database,
        "auth_configuration": bool(
            _https_origin(settings.supabase_url, exact_origin=False)
            and settings.supabase_auth_configured
            and settings.supabase_admin_configured
        ),
        "https_origins": bool(settings.cors_origin_list)
        and all(_https_origin(origin) for origin in settings.cors_origin_list),
        # Neither generic checkout nor a sandbox event proves live settlement.
        "verified_payment_mode": settings.gcash_mode.strip().lower() == "disabled",
    }
    if all(checks.values()):
        checks.update(probe_database(settings))
    else:
        checks.update({"schema": False, "private_grants": False})
    return _report("runtime_configuration", checks)


def _private_storage_ready() -> bool:
    configured = os.getenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", "")
    if not configured:
        return False
    location = Path(configured)
    repository = Path(__file__).resolve().parents[3]
    try:
        if not location.is_absolute() or not location.is_dir():
            return False
        if any(item.is_symlink() for item in (location, *location.parents)):
            return False
        resolved = location.resolve()
        if resolved == repository or repository in resolved.parents:
            return False
        if os.name != "nt" and stat.S_IMODE(location.stat().st_mode) & 0o077:
            return False
        return os.access(location, os.R_OK | os.W_OK | os.X_OK)
    except OSError:
        return False


def _owner_ready(settings: Settings) -> bool:
    owner = configured_employee_owner_id()
    if owner is None:
        return False
    try:
        with _connect(settings) as connection:
            row = connection.execute(
                """SELECT EXISTS (SELECT 1 FROM core.users u
                WHERE u.id=%s AND u.status='active'
                AND EXISTS (SELECT 1 FROM core.devices d WHERE d.user_id=u.id AND d.status='active')
                AND EXISTS (SELECT 1 FROM core.user_roles ur JOIN core.roles r ON r.id=ur.role_id
                            WHERE ur.user_id=u.id AND r.code IN ('management','employee','collector')))""",
                (owner,),
            ).fetchone()
            return bool(row and row[0])
    except (psycopg.Error, ValueError):
        return False


def check_activation(settings: Settings) -> PreflightReport:
    from .first_loan_documents import template_bundle
    from .first_loan_repository import FirstLoanConflict
    from .privacy_record_repository import privacy_package

    checks = check_runtime(settings)["checks"]
    checks["private_evidence_storage"] = _private_storage_ready()
    checks["privacy_package"] = privacy_package().get("issuable") is True
    try:
        template_bundle()
        checks["legal_templates"] = True
    except (FirstLoanConflict, OSError, ValueError, KeyError, TypeError):
        checks["legal_templates"] = False
    converter = Path(os.getenv("GILBIC_OFFICE_DOCUMENT_CONVERTER", ""))
    checks["document_converter"] = bool(
        converter.is_absolute()
        and converter.is_file()
        and os.access(converter, os.X_OK)
    )
    checks["credential_email"] = settings.credential_smtp_configured
    checks["employee_owner"] = _owner_ready(settings) if checks["schema"] else False
    return _report("activation_configuration_only", checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=("runtime", "activation"), default="runtime"
    )
    args = parser.parse_args()
    try:
        settings = get_settings()
        result = (
            check_activation(settings)
            if args.profile == "activation"
            else check_runtime(settings)
        )
    except (ValueError, OSError):
        result = _report("invalid_configuration", {"settings": False})
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
