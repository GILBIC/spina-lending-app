"""Collector liabilities, elapsed assessments and payouts on fresh schema0157."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_accounting_increment_private_barrier_postgres.py",
    "test_collector_liability_accounting_postgres.py",
    "test_collector_liability_authority_postgres.py",
    "test_collector_liability_manifest_postgres.py",
    "test_collector_liability_no_cash_constituents_postgres.py",
    "test_collector_liability_accounting_api.py",
    "test_collector_liability_accounting_projection.py",
    "test_collector_accounting_capability.py",
    "test_collector_control_schedule_postgres.py",
    "test_collector_control_schedule_api.py",
    "test_collector_cash_flow_reporting.py",
    "test_collector_cash_flow_postgres.py",
    "test_elapsed_period_assessment_postgres.py",
    "test_elapsed_period_assessment_repository_postgres.py",
    "test_elapsed_period_assessment_controls_postgres.py",
    "test_elapsed_assessment_chart_postgres.py",
    "test_elapsed_assessment_review_projection.py",
    "test_elapsed_period_assessment_api.py",
    "test_loan_payout_accounting_postgres.py",
    "test_loan_payout_accounting_boundaries_postgres.py",
    "test_loan_payout_accounting_concurrency_postgres.py",
    "test_loan_payout_control_identity_postgres.py",
    "test_loan_payout_manifest_postgres.py",
    "test_loan_payout_accounting_api.py",
    "test_loan_payout_accounting_projection.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=157, tests=TESTS, timeout_seconds=1200)
    )
