"""Actual transfer legs and retained review on fresh schema0151, no skipped proof."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_treasury_transfer_accounting_postgres.py",
    "test_treasury_transfer_accounting_boundaries_postgres.py",
    "test_treasury_transfer_control_identity_postgres.py",
    "test_treasury_transfer_accounting_concurrency_postgres.py",
    "test_treasury_transfer_accounting_api.py",
    "test_treasury_transfer_accounting_projection.py",
    "test_transfer_cash_flow_reporting.py",
    "test_transfer_cash_flow_postgres.py",
    "test_period_review_manifest_postgres.py",
    "test_period_review_manifest_concurrency_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=151, tests=TESTS, timeout_seconds=600)
    )
