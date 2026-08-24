from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0104_add_protected_regular_advance_allocation_basis.sql"
)


def test_protected_regular_advance_basis_is_explicit_and_backward_compatible() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "future_advance_oldest_first" in sql
    assert "oldest_due_first" in sql
    assert "voluntary_extra_tail" in sql
    assert "exact_covered_date" in sql
    assert "borrower-directed regular advance" in sql
