"""Regular first payments and existing 7x7 paths on the actual schema 0155."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_treasury_application_accounting_postgres.py",
    "test_treasury_application_accounting_boundaries_postgres.py",
    "test_treasury_application_accounting_concurrency_postgres.py",
    "test_treasury_application_accounting_sequence_postgres.py",
    "test_treasury_application_chart_drift_postgres.py",
    "test_treasury_application_accounting_api.py",
    "test_treasury_application_accounting_projection.py",
    "test_regular_treasury_application_postgres.py",
    "test_regular_treasury_application_boundaries_postgres.py",
    "test_regular_treasury_application_concurrency_postgres.py",
    "test_regular_application_origin_chart_postgres.py",
    "test_regular_treasury_application_projection.py",
    "test_elapsed_period_assessment_postgres.py",
    "test_elapsed_period_assessment_controls_postgres.py",
    "test_elapsed_assessment_chart_postgres.py",
    "test_elapsed_period_assessment_repository_postgres.py",
    "test_elapsed_period_assessment_api.py",
    "test_elapsed_assessment_review_projection.py",
    "test_accounting_increment_private_barrier_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=155, tests=TESTS, timeout_seconds=1800)
    )
