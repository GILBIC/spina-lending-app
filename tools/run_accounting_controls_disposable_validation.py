"""Verify the new accounting controls on fresh schema0144, with zero skips.

This proves the bounded controls, not a complete lending/annual reporting cycle.
The existing0092 accounting cycle verifier remains an independent legacy proof.
"""

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
TESTS = (
    "test_accounting_book_postgres.py",
    "test_financial_statement_snapshot_postgres.py",
    "test_accounting_book_isolation_postgres.py",
    "test_period_close_postgres.py",
    "test_period_close_loss_postgres.py",
    "test_period_close_unfiltered_postgres.py",
    "test_source_close_guard_postgres.py",
    "test_period_source_repository_postgres.py",
    "test_accounting_book_api.py",
    "test_financial_statements.py",
    "test_period_source_api.py",
    "test_period_close_api_contract.py",
    "test_database_book_pin.py",
    "test_database_transactions.py",
    "test_database_connection_normalization.py",
)


def main(
    *, bootstrap_through=144, extra_migrations=(), tests=TESTS, timeout_seconds=300
) -> int:
    if os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise SystemExit("Explicit SPINA_ALLOW_DISPOSABLE_DATABASE=1 is required.")
    params = disposable._safe_local_connection_params(
        os.environ.get("ACCOUNTING_CONTROLS_DATABASE_URL", "")
    )
    if params["dbname"].startswith(PREFIX) or any(
        k in params for k in ("options", "passfile")
    ):
        raise SystemExit(
            "Use an explicit loopback administrative database, without test prefix/options/passfile."
        )
    disposable._clear_endpoint_environment()
    disposable.BOOTSTRAP_THROUGH = bootstrap_through
    disposable.TEST_DATABASE_PREFIX = PREFIX
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
        for migration in extra_migrations:
            path = ROOT / "gilbic_backend/sql" / migration
            with psycopg.connect(test_url) as connection:
                connection.execute(path.read_text(encoding="utf-8"))
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("GILBIC_", "SPINA_", "SUPABASE_", "PG"))
            and k not in {"DATABASE_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"}
        }
        env.update(
            GILBIC_DATABASE_URL=test_url,
            GILBIC_TEST_DATABASE_URL=test_url,
            SPINA_ALLOW_DISPOSABLE_DATABASE="1",
            SPINA_CURRENT_SCHEMA_THROUGH=str(bootstrap_through),
            PYTHONDONTWRITEBYTECODE="1",
            # The hosted database has no JIT. LLVM compilation of the composed
            # source checks dominates short-lived synthetic databases on Linux.
            # Keep the same SQL, assertions and deadlines under that execution
            # mode, replacing rather than inheriting ambient libpq options.
            PGOPTIONS="-c jit=off",
        )
        if os.getenv("SPINA_POSTGRES_BIN"):
            env["SPINA_POSTGRES_BIN"] = os.environ["SPINA_POSTGRES_BIN"]
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
        with tempfile.TemporaryDirectory(
            prefix="spina-accounting-controls-"
        ) as scratch:
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
                    *(str(ROOT / "gilbic_backend/tests" / test) for test in tests),
                ],
                cwd=ROOT,
                env=env,
                check=False,
                timeout=timeout_seconds,
            )
            if result.returncode:
                return result.returncode
            suites = ET.parse(junit).getroot().iter("testsuite")
            total = 0
            for suite in suites:
                total += int(suite.attrib["tests"])
                if any(
                    int(suite.attrib.get(k, "0"))
                    for k in ("skipped", "errors", "failures")
                ):
                    raise SystemExit(
                        "Accounting controls verification forbids skipped or failed checks."
                    )
            if total < 50:
                raise SystemExit(
                    "Accounting controls verification collected fewer than expected checks."
                )
            print(
                f"Accounting controls verified: {total} checks, zero skips, fresh schema{bootstrap_through:04d} with extras {extra_migrations}."
            )
        return 0
    finally:
        if created:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                # The reusable helper's older suffix allowlist excludes24char
                # Treasury names, so verify this exact generated name here.
                assert name.startswith(PREFIX) and len(name[len(PREFIX) :]) == 24
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    raise SystemExit(main())
