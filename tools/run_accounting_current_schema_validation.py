"""Adapter regressions plus isolated final-schema close and populated recovery.

The final-schema cycle creates its own template0 database and never reinstalls
older migrations from historical regression fixtures. Coverage remains bounded
to the supported adapters; this is not a complete lending readiness declaration.
"""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_treasury_application_accounting_postgres.py",
    "test_treasury_application_accounting_boundaries_postgres.py",
    "test_treasury_application_accounting_concurrency_postgres.py",
    "test_treasury_application_accounting_sequence_postgres.py",
    "test_treasury_application_chart_drift_postgres.py",
    "test_treasury_application_accounting_api.py",
    "test_treasury_application_accounting_projection.py",
    "test_retained_cutoff_assessment_postgres.py",
    "test_retained_cutoff_assessment_concurrency_postgres.py",
    "test_retained_cutoff_assessment_repository_postgres.py",
    "test_retained_cutoff_assessment_api.py",
    "test_retained_cutoff_assessment_precision.py",
    "test_retained_cutoff_assessment_chart_postgres.py",
    "test_proven_source_composition_postgres.py",
    "test_proven_source_composition_controls_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=152, tests=TESTS, timeout_seconds=1800)
    )
