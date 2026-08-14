from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0091_add_protected_period_close.sql").read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_period_close_migration_is_transactional_management_only_and_explicit() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.period.close.prepare",
        "accounting.period.close.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    assert "require_period_close_management_actor" in LOWER
    assert "automatic_source_posting" in LOWER
    assert "false as period_reopen_enabled" in LOWER


def test_close_reuses_existing_general_journal_and_retained_earnings() -> None:
    assert "period_close_preparations" in LOWER
    assert "period_close_account_snapshots" in LOWER
    assert "period_close_postings" in LOWER
    assert "source_type, source_reference, source_event_key" in LOWER
    assert "'period_close'" in LOWER
    assert "account.system_key = 'retained_earnings'" in LOWER
    assert "retained_account.code <> '3100'" in LOWER
    assert "account_type in ('income', 'expense')" in LOWER
    assert "close temporary account to retained earnings" in LOWER
    assert "transfer period profit or loss to retained earnings" in LOWER
    assert "create table if not exists accounting.journal_entries" not in LOWER
    assert "create table if not exists accounting.accounts" not in LOWER


def test_review_freezes_ordinary_posting_and_direct_close_is_blocked() -> None:
    assert "accounting periods in review are frozen" in LOWER
    assert "closed accounting periods reject all new journal drafts" in LOWER
    assert "accounting period cannot enter review while draft journal entries remain" in LOWER
    assert "use the protected formal period-close posting workflow" in LOWER
    assert "period_close_transition_allowed" in LOWER
    assert "protected_review_close" in LOWER
    assert "period_row.status = 'review'" in LOWER
    assert "entry_row.source_type = 'period_close'" in LOWER


def test_close_journal_and_audits_are_immutable_and_not_manually_reversible() -> None:
    assert "period-close preparation, snapshot and posting audit rows are immutable" in LOWER
    assert "formal period-close journals are system generated and immutable" in LOWER
    assert "formal period-close journal lines are system generated and immutable" in LOWER
    assert "a formal period-close journal cannot be reversed" in LOWER
    assert "closed accounting periods are immutable and cannot be reopened in v1" in LOWER
    assert "period_close_force_audit_failure" in LOWER


def test_close_revalidates_balances_and_requires_zero_temporary_accounts() -> None:
    for fragment in (
        "posted ledger balances changed after formal period-close preparation",
        "temporary-account close snapshot no longer matches the posted ledger",
        "prepared temporary-account closing lines changed",
        "prepared retained earnings close line changed",
        "temporary income/expense accounts remain non-zero",
        "retained earnings after close does not reconcile",
    ):
        assert fragment in LOWER
    assert "preparation.retained_earnings_balance_before + preparation.net_income" in LOWER
    assert "true as protected_period_close_enabled" in LOWER
    assert "true as retained_earnings_close_enabled" in LOWER
    assert "true as closed_period_posting_protection_enabled" in LOWER
