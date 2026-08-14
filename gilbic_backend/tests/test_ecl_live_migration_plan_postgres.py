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
        _transaction_body((SQL_ROOT / migration_name).read_text(encoding="utf-8"))
    )


def test_live_plan_upgrades_existing_a3_then_exact_a4_with_only_forward_suffixes() -> None:
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
        "0079_add_ecl_remeasurement_writeoff_recovery.sql",
        "0080_harden_ecl_post_writeoff_boundaries.sql",
    ]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")

        try:
            # Existing hardened A3: only A4+A5 forward suffix may be selected.
            for migration_name in names[:7]:
                _apply(connection, migration_name)
            selected_from_a3 = planner._select_missing_forward_migrations(connection)
            assert [path.name for path in selected_from_a3] == names[7:]

            # Reproduce the exact currently-live A4 milestone: 0070-0078 installed.
            for migration_name in names[7:9]:
                _apply(connection, migration_name)
            selected_from_a4 = planner._select_missing_forward_migrations(connection)
            assert [path.name for path in selected_from_a4] == names[9:]

            history_before_a5 = planner.ecl._history_counts(connection)
            for migration_name in names[9:]:
                _apply(connection, migration_name)
            history_after_a5 = planner.ecl._history_counts(connection)
            assert history_after_a5 == history_before_a5

            # Fully installed A5 must be a no-op and all protected controls verify.
            assert planner._select_missing_forward_migrations(connection) == ()
            a5_summary = planner.ecl._verify(connection)[5]
            assert a5_summary[10:] == (True, False)
        finally:
            connection.rollback()
