from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0035_add_verified_contract_schedule_registration.sql"
).read_text(encoding="utf-8")


def test_stage5e43_adds_management_permission_and_immutable_audit() -> None:
    assert "lending.contract_schedule.manage" in SQL
    assert "loan_contract_schedule_registrations" in SQL
    assert "verified_by_user_id" in SQL
    assert "evidence_reference" in SQL
    assert "verification_note" in SQL
    assert "registration records are immutable" in SQL


def test_stage5e43_preserves_contract_terms_as_evidence() -> None:
    assert "guard_contract_installment_immutability" in SQL
    assert "guard_contract_schedule_terms" in SQL
    assert "active' AND NEW.status = 'superseded'" in SQL
    assert "Contract schedules cannot be deleted" in SQL


def test_stage5e43_migration_does_not_backfill_or_post() -> None:
    lowered = SQL.lower()
    assert "insert into lending.loan_contract_schedules" not in lowered
    assert "insert into lending.loan_contract_installments" not in lowered
    assert "update lending.loans" not in lowered
    assert "explicit_default_label" not in lowered
    assert "accounting.journal" not in lowered
    assert "ecl_amount" not in lowered
