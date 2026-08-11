from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0044_harden_collection_void_reversal_evidence.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_void_evidence_hardening_is_transactional_and_install_only() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "UPDATE lending.collection_transactions" not in sql
    assert "SELECT accounting.reverse_posted_regular_collection" not in sql


def test_collection_void_audit_becomes_database_immutable() -> None:
    sql = migration_sql()
    assert "guard_collection_transaction_void_audit_immutability" in sql
    assert "lending_collection_transaction_void_audit_guard" in sql
    assert "BEFORE UPDATE OR DELETE ON lending.collection_transaction_voids" in sql
    assert "Collection void audit records are immutable" in sql


def test_operational_void_must_exactly_match_immutable_evidence() -> None:
    sql = migration_sql()
    assert "guard_collection_void_transition_evidence" in sql
    assert "voided_by_user_id IS DISTINCT FROM NEW.voided_by_user_id" in sql
    assert "void_record.voided_at IS DISTINCT FROM NEW.voided_at" in sql
    assert "btrim(void_record.reason) IS DISTINCT FROM btrim(NEW.void_reason)" in sql
    assert "A collection cannot be voided without immutable collection-void evidence" in sql


def test_trigger_order_proves_evidence_before_reversal_before_fail_closed_guard() -> None:
    sql = migration_sql()
    assert "DROP TRIGGER IF EXISTS accounting_00_regular_collection_void_reversal" in sql
    assert "CREATE TRIGGER accounting_00_collection_void_evidence_guard" in sql
    assert "CREATE TRIGGER accounting_01_regular_collection_void_reversal" in sql
    assert "perform_controlled_regular_collection_void_reversal" in sql
