from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "gilbic_backend" / "sql" / "0108_add_7x7_extra_principal_bridge.sql"


def _migration_sql() -> str:
    assert MIGRATION.is_file(), f"Required bridge migration is missing: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def test_0108_is_forward_only_and_preserves_historical_evidence() -> None:
    sql = _migration_sql()
    normalized = " ".join(sql.split()).lower()

    assert "drop table" not in normalized
    assert "truncate" not in normalized
    assert "delete from lending.seven_by_seven_extra_principal" not in normalized
    assert "update lending.seven_by_seven_extra_principal_adjustments" not in normalized


def test_0108_defines_exact_reversal_and_refund_due_evidence() -> None:
    sql = _migration_sql().lower()

    required_relations = (
        "lending.seven_by_seven_extra_principal_reversal_requests",
        "lending.seven_by_seven_extra_principal_reversals",
        "lending.seven_by_seven_extra_principal_reversal_items",
        "lending.loan_unused_advance_refund_due_approvals",
        "lending.loan_unused_advance_refund_due_approval_items",
        "lending.loan_unused_advance_refund_due_releases",
        "lending.loan_unused_advance_refund_due_release_items",
        "lending.loan_unused_advance_refund_due_status",
        "lending.seven_by_seven_extra_principal_reversal_status",
    )
    for relation in required_relations:
        assert relation in sql

    assert "last_extra_principal_adjustment_id drop not null" in " ".join(sql.split())
    assert "loan_installment_active_advance" in sql


def test_0108_protects_append_only_tables_with_transaction_local_sessions() -> None:
    sql = _migration_sql().lower()

    assert "current_setting(required_session_setting, true)" in sql
    assert "'spina.extra_principal_reversal_write'" in sql
    assert "'spina.refund_due_approval_write'" in sql
    assert "'spina.refund_due_release_write'" in sql
    assert sql.count("before insert or update or delete") >= 7
