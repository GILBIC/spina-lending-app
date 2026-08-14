from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0081_add_protected_initial_capital_funding.sql"
).read_text(encoding="utf-8")


def test_initial_capital_funding_reuses_general_journal_without_opening_balance_workbook() -> None:
    assert "accounting.initial_capital.evidence.record" in SQL
    assert "accounting.initial_capital.prepare" in SQL
    assert "accounting.initial_capital.post" in SQL
    assert "accounting.journal_entries" in SQL
    assert "accounting.journal_lines" in SQL
    assert "accounting.post_journal_entry" in SQL
    assert "source_type,\n        source_reference, source_event_key" in SQL
    assert "'initial_capital_funding'" in SQL
    assert "opening_balance_workbooks" not in SQL
    assert "opening_balance_workbook_lines" not in SQL
    assert "synthetic_opening_balance_required" in SQL
    assert "false AS synthetic_opening_balance_required" in SQL
    assert "false AS automatic_source_posting" in SQL


def test_initial_capital_funding_is_evidence_backed_and_exact() -> None:
    assert "initial_capital_funding_evidence" in SQL
    assert "evidence_source" in SQL
    assert "evidence_reference" in SQL
    assert "evidence_digest" in SQL
    assert "evidence_note" in SQL
    assert "idempotency_key" in SQL
    assert "immutable retry identity" in SQL
    assert "cash_office" in SQL
    assert "cash_bank_gcash" in SQL
    assert "capital_account.code <> '3000'" in SQL
    assert "Dr selected cash/bank / Cr Capital" in SQL
    assert "initial_capital_funding_v1" in SQL


def test_initial_capital_journal_cannot_use_generic_mutation_or_manual_reversal() -> None:
    assert "guard_initial_capital_journal_entry_change" in SQL
    assert "guard_initial_capital_journal_line_change" in SQL
    assert "require the protected Management posting function" in SQL
    assert "cannot be reversed through the manual General Journal" in SQL
    assert "initial_capital_force_audit_failure" in SQL
    assert "Forced initial-capital audit failure" in SQL
