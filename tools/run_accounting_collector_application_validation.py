"""Credit-funded custody, private scopes, exact journals and recovery on 0160."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_collector_credit_application_postgres.py",
    "test_collector_credit_application_boundaries_postgres.py",
    "test_collector_credit_application_contract_postgres.py",
    "test_collector_credit_application_reporting_postgres.py",
    "test_collector_credit_application_recovery_postgres.py",
    "test_collector_application_reference.py",
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
    "test_accounting_increment_private_barrier_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=160, tests=TESTS, timeout_seconds=1200)
    )
