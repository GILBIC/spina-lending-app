"""Native original payout provenance and preserved payout controls at schema0159."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_native_payout_regular_origin_postgres.py",
    "test_native_payout_regular_origin_boundaries_postgres.py",
    "test_loan_payout_accounting_postgres.py",
    "test_loan_payout_accounting_boundaries_postgres.py",
    "test_loan_payout_accounting_concurrency_postgres.py",
    "test_loan_payout_control_identity_postgres.py",
    "test_loan_payout_manifest_postgres.py",
    "test_loan_payout_accounting_api.py",
    "test_loan_payout_accounting_projection.py",
    "test_accounting_increment_private_barrier_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=159, tests=TESTS, timeout_seconds=900)
    )
