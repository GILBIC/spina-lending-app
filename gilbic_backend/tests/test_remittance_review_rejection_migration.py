from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0102_add_remittance_review_and_rejection.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_review_and_rejection_history_is_permanent_and_itemized() -> None:
    sql = _sql()

    assert "collection_remittance_reviews" in sql
    assert "collection_remittance_rejections" in sql
    assert "reason text not null" in sql
    assert "on delete restrict" in sql
    assert "drop constraint if exists collection_remittance_items_transaction_id_key" in sql
    assert "collection_remittance_items_transaction_idx" in sql


def test_rejection_unlock_is_narrowly_guarded() -> None:
    sql = _sql()

    assert "create or replace function lending.prevent_locked_collection_mutation" in sql
    assert "rejected_remittance" in sql
    assert "new.remittance_id is null" in sql
    assert "new.is_locked = false" in sql
    assert "new_financial = old_financial" in sql
    assert "remitted collection transactions are permanently locked" in sql
