from pathlib import Path

import pytest
from pydantic import ValidationError

from gilbic_backend.employee_operations_models import ACTION_ADAPTER

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0134_add_cash_disbursement_permission.sql"
REPOSITORY = ROOT / "src" / "gilbic_backend" / "employee_operations_repository.py"


def command(**overrides):
    value = {
        "action": "cash_disbursement_prepare",
        "request_id": "10000000-0000-4000-8000-000000000001",
        "id": "20000000-0000-4000-8000-000000000001",
        "expected_version": 0,
        "as_of": "2026-10-01",
        "payee": "Electric utility",
        "purpose": "September office electricity",
        "amount": "1250.50",
        "expense_account_code": "5210",
        "cash_account_code": "1010",
        "evidence_reference": "OR-UTIL-1001",
        "evidence": "Reviewed original utility receipt",
    }
    value.update(overrides)
    return value


def test_cash_disbursement_command_is_strict_and_uses_decimal_text():
    parsed = ACTION_ADAPTER.validate_python(command())
    assert parsed.action == "cash_disbursement_prepare"
    assert format(parsed.amount, ".2f") == "1250.50"
    assert parsed.expense_account_code == "5210"
    assert parsed.cash_account_code == "1010"

    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(command(amount=1250.50))
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(command(amount="0.00"))
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(command(expense_account_code="3000"))
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(command(cash_account_code="1020"))


def test_cash_disbursement_permission_is_only_employee_and_management():
    assert MIGRATION.exists(), "0134 cash-disbursement permission migration is required"
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "cash_disbursement.prepare" in sql
    compact = "".join(sql.split())
    assert "role.codein('employee','management')" in compact
    assert "collector" not in sql


def test_cash_disbursement_repository_derives_balanced_expense_to_cash_lines_only():
    source = REPOSITORY.read_text(encoding="utf-8")
    assert "def do_cash_disbursement_prepare" in source
    assert 'permission="cash_disbursement.prepare"' in source
    assert '"debit": money_text(c.amount)' in source
    assert '"credit": money_text(c.amount)' in source
    assert "expense_account_code" in source
    assert "cash_account_code" in source
    assert "post_manual_journal_entry" not in source[source.index("def do_cash_disbursement_prepare"):source.index("def do_accounting_prepare")]


def test_cash_disbursement_is_a_create_only_accounting_preparation():
    source = REPOSITORY.read_text(encoding="utf-8")
    assert '"cash_disbursement_prepare": "accounting_preparations"' in source
