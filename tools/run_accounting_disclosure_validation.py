"""Exact mixed-journal disclosures, private scopes and recovery on schema0158."""

import run_accounting_controls_disposable_validation as controls

TESTS = (
    "test_journal_disclosures.py",
    "test_journal_disclosure_postgres.py",
    "test_journal_disclosure_controls_postgres.py",
    "test_journal_disclosure_collector_postgres.py",
    "test_collector_credit_application_reporting_postgres.py",
    "test_journal_disclosure_api.py",
    "test_reporting_policy_postgres.py",
    "test_reporting_evidence_api.py",
    "test_financial_statements.py",
    "test_financial_statement_snapshot_postgres.py",
    "test_accounting_increment_private_barrier_postgres.py",
    "test_current_schema_accounting_cycle_postgres.py",
    "test_collector_cash_flow_reporting.py",
    "test_collector_cash_flow_postgres.py",
)

if __name__ == "__main__":
    raise SystemExit(
        controls.main(bootstrap_through=158, tests=TESTS, timeout_seconds=1200)
    )
