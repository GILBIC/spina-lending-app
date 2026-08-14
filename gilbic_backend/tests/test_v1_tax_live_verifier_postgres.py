from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools" / "apply_v1_tax_accounting_migrations.py"

TAX_DATA_RELATIONS = (
    "accounting.v1_tax_rule_evidence",
    "accounting.v1_dst_evidence",
    "accounting.v1_percentage_tax_evidence",
    "accounting.v1_tax_liability_preparations",
    "accounting.v1_tax_liability_postings",
    "accounting.v1_tax_return_evidence",
    "accounting.v1_tax_return_liability_items",
    "accounting.v1_tax_payment_evidence",
    "accounting.v1_tax_settlement_preparations",
    "accounting.v1_tax_settlement_postings",
    "accounting.v1_tax_adjustment_evidence",
    "accounting.v1_tax_adjustment_preparations",
    "accounting.v1_tax_adjustment_postings",
    "accounting.v1_tax_additional_amendment_evidence",
    "accounting.v1_tax_additional_liability_preparations",
    "accounting.v1_tax_additional_liability_postings",
    "accounting.v1_tax_additional_payment_evidence",
    "accounting.v1_tax_additional_settlement_preparations",
    "accounting.v1_tax_additional_settlement_postings",
    "accounting.v1_tax_recoverable_refund_evidence",
    "accounting.v1_tax_recoverable_refund_preparations",
    "accounting.v1_tax_recoverable_refund_postings",
    "accounting.v1_tax_recoverable_credit_evidence",
    "accounting.v1_tax_recoverable_credit_preparations",
    "accounting.v1_tax_recoverable_credit_postings",
)


def _history_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    relations = (
        "lending.loans",
        "lending.loan_disbursement_events",
        "lending.collection_transactions",
        "accounting.journal_entries",
        "accounting.journal_lines",
        "accounting.journal_events",
        "core.audit_logs",
    )
    return tuple(
        int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])
        for relation in relations
    )


def test_schema_control_live_verifier_installs_0082_through_0090_without_business_rows() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        before_history = _history_counts(connection)

    env = os.environ.copy()
    env["GILBIC_TEST_DATABASE_URL"] = DATABASE_URL
    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--database-url-env",
            "GILBIC_TEST_DATABASE_URL",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "A6.2 V1 tax live schema/control verification passed" in completed.stdout
    assert "protected_history_unchanged=True" in completed.stdout
    assert "protected_tax_rows_unchanged=True" in completed.stdout
    assert "automatic_source_posting=False" in completed.stdout

    with psycopg.connect(DATABASE_URL) as connection:
        assert _history_counts(connection) == before_history
        for relation in TAX_DATA_RELATIONS:
            assert connection.execute(
                f"SELECT count(*) FROM {relation}"
            ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT evidence_backed_tax_readiness_enabled, tax_posting_enabled,
                   automatic_source_posting
            FROM accounting.v1_tax_readiness_summary
            """
        ).fetchone() == (True, False, False)
        assert connection.execute(
            "SELECT * FROM accounting.v1_tax_recoverable_controls"
        ).fetchone() == (True, True, False, False)
