"""Verify Collector recovery against the current production schema, without skips."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "spina_treasury_validation_"
BOOTSTRAP_THROUGH = 140
TESTS = (
    "test_collector_payment_undo_postgres.py",
    "test_collector_payment_undo_api.py",
    "test_combined_collection_renewal_workflow_postgres.py",
    "test_collection_correction_api.py",
    "test_collection_correction_repository.py",
    "test_collection_correction_authority.py",
    "test_collection_void_api.py",
    "test_treasury_collection_posting_postgres.py",
    "test_collector_route_api.py",
    "test_collector_route_repository.py",
    "test_other_area_repository.py",
)


def main() -> int:
    if os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise SystemExit("Explicit SPINA_ALLOW_DISPOSABLE_DATABASE=1 is required.")
    params = disposable._safe_local_connection_params(
        os.environ.get("COLLECTOR_RECOVERY_DATABASE_URL", "")
    )
    if params["dbname"].startswith(PREFIX) or any(
        key in params for key in ("options", "passfile")
    ):
        raise SystemExit(
            "Use a loopback administrative database without options/passfile."
        )
    disposable._clear_endpoint_environment()
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
    name = PREFIX + uuid4().hex[:24]
    admin_url = disposable._conninfo_for_database(params, "postgres")
    test_url = disposable._conninfo_for_database(params, name)
    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
        created = True
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GILBIC_", "SPINA_", "SUPABASE_", "PG"))
            and key not in {"DATABASE_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"}
        }
        env.update(
            GILBIC_DATABASE_URL=test_url,
            GILBIC_TEST_DATABASE_URL=test_url,
            SPINA_ALLOW_DISPOSABLE_DATABASE="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        env["PYTHONPATH"] = os.pathsep.join(
            str(ROOT / part)
            for part in (
                "gilbic_backend/src",
                "spina_backend_mobile/src",
                "gilbic_backend/tests",
                "tools",
                ".",
            )
        )
        with tempfile.TemporaryDirectory(prefix="spina-collector-recovery-") as scratch:
            junit = Path(scratch) / "result.xml"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(Path(scratch) / "pytest"),
                    "--junitxml",
                    str(junit),
                    *(str(ROOT / "gilbic_backend/tests" / test) for test in TESTS),
                ],
                cwd=ROOT,
                env=env,
                check=False,
                timeout=600,
            )
            if result.returncode:
                return result.returncode
            total = 0
            for suite in ET.parse(junit).getroot().iter("testsuite"):
                total += int(suite.attrib["tests"])
                if any(
                    int(suite.attrib.get(key, "0"))
                    for key in ("skipped", "errors", "failures")
                ):
                    raise SystemExit(
                        "Collector recovery verification forbids skipped or failed checks."
                    )
            if total < 50:
                raise SystemExit(
                    "Collector recovery verification collected too few checks."
                )
            print(
                f"Collector recovery verified: {total} checks, zero skips, schema{BOOTSTRAP_THROUGH:04d}."
            )
        return 0
    finally:
        if created:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    raise SystemExit(main())
