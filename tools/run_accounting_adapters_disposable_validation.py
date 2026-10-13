"""Composed receipts, generic liabilities, legacy source checks and reporting.

0149 applications and0151 cutoff assessment are verified separately until their
complete protected flows can join this admission suite. This bounded checkpoint
uses148 plus independent150, never silently counts unsupported flows as tested.
"""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    *controls.TESTS,
    "test_treasury_receipt_accounting_postgres.py",
    "test_treasury_receipt_accounting_boundaries_postgres.py",
    "test_treasury_receipt_accounting_concurrency_postgres.py",
    "test_treasury_receipt_accounting_api.py",
    "test_liability_control_postgres.py",
    "test_liability_control_concurrency_postgres.py",
    "test_liability_control_api.py",
    "test_liability_chart_identity_postgres.py",
    "test_legacy_source_completeness_postgres.py",
    "test_accounting_source_composition_postgres.py",
    "test_reporting_policy_postgres.py",
    "test_reporting_pack_postgres.py",
    "test_financial_reporting_supplement.py",
    "test_reporting_evidence_api.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(
            bootstrap_through=148,
            extra_migrations=("0150_add_reporting_evidence.sql",),
            tests=TESTS,
        )
    )
