from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

ROOT = Path(__file__).resolve().parents[2]
SQL_ROOT = ROOT / "gilbic_backend" / "sql"
TOOLS_ROOT = ROOT / "tools"

_spec = importlib.util.spec_from_file_location(
    "ecl_live_plan",
    TOOLS_ROOT / "apply_ecl_live_migrations_version_aware.py",
)
assert _spec is not None and _spec.loader is not None
planner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(planner)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _apply(connection: psycopg.Connection, migration_name: str) -> None:
    connection.execute(
        _transaction_body(
            (SQL_ROOT / migration_name).read_text(encoding="utf-8")
        )
    )


def test_live_plan_upgrades_existing_a3_with_only_0077_0078_and_then_is_noop() -> None:
    assert DATABASE_URL is not None
    names = [path.name for path in planner.ecl.MIGRATIONS]
    assert names == [
        "0070_add_ecl_credit_risk_labels.sql",
        "0071_harden_ecl_cash_recovery_chronology.sql",
        "0072_add_ecl_quantitative_input_readiness.sql",
        "0073_add_ecl_forward_looking_evidence_governance.sql",
        "0074_integrate_ecl_forward_looking_readiness.sql",
        "0075_add_read_only_quantitative_ecl_measurement.sql",
        "0076_harden_read_only_quantitative_ecl_measurement.sql",
        "0077_add_protected_ecl_allowance_posting.sql",
        "0078_harden_ecl_allowance_posting_queue.sql",
    ]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")

        try:
            for migration_name in names[:7]:
                _apply(connection, migration_name)

            selected = planner._select_missing_forward_migrations(connection)
            assert [path.name for path in selected] == names[7:]

            # This is the exact live upgrade shape that failed when the installer
            # replayed 0074/0075/0076 over an already-hardened A3 database.
            for migration in selected:
                _apply(connection, migration.name)

            selected_after_a4 = planner._select_missing_forward_migrations(connection)
            assert selected_after_a4 == ()
        finally:
            connection.rollback()
