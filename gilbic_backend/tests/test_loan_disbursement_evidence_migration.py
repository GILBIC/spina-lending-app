from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0045_add_authoritative_loan_disbursement_evidence.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_disbursement_evidence_migration_is_transactional_and_install_only() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "lending.loan_disbursement_events" in sql
    assert "accounting.loan_disbursement_source_readiness" in sql
    assert "accounting.loan_disbursement.evidence.manage" in sql
    assert "INSERT INTO lending.loan_disbursement_events" in sql
    # Installation defines the function but never invokes it or backfills from loans.
    assert "SELECT accounting.record_loan_disbursement_evidence" not in sql
    assert "INSERT INTO lending.loan_disbursement_events\nSELECT" not in sql


def test_loan_row_or_release_date_is_not_accepted_as_funding_evidence() -> None:
    sql = migration_sql()
    assert "missing_disbursement_evidence" in sql
    assert "A lending.loans row/date_released alone is never treated as proof" in sql
    assert "LEFT JOIN lending.loan_disbursement_events event" in sql
    assert "AND event.is_voided = false" in sql


def test_disbursement_evidence_is_immutable_and_has_controlled_correction_path() -> None:
    sql = migration_sql()
    assert "guard_loan_disbursement_event_write" in sql
    assert "Loan disbursement evidence is immutable and cannot be deleted" in sql
    assert "lending_one_active_disbursement_per_loan_uidx" in sql
    assert "void_loan_disbursement_evidence" in sql
    assert "different active disbursement evidence" in sql
    assert "journal history" in sql


def test_source_evidence_requires_explicit_cash_account_and_reconciliation() -> None:
    sql = migration_sql()
    assert "cash_office" in sql
    assert "cash_collector_custody" in sql
    assert "cash_bank_gcash" in sql
    assert "unreconciled_release_components" in sql
    assert "release_date_mismatch" in sql
    assert "loan_changed_after_evidence" in sql
    assert "source_evidence_ready" in sql


def test_renewals_deductions_and_restructures_remain_policy_blocked() -> None:
    sql = migration_sql()
    assert "renewal_or_restructure_policy_review" in sql
    assert "deduction_or_settlement_policy_review" in sql
    assert "event.event_kind <> 'new_loan_release'" in sql
    assert "event.settlement_amount <> 0 OR event.other_deduction_amount <> 0" in sql


def test_stage5d19_does_not_create_accounting_lines_or_enable_automatic_posting() -> None:
    sql = migration_sql()
    assert "false AS journal_lines_enabled" in sql
    assert "false AS automatic_source_posting" in sql
    assert "does not authorize journal lines or automatic posting" in sql
    assert "INSERT INTO accounting.journal_entries" not in sql
    assert "INSERT INTO accounting.journal_lines" not in sql
