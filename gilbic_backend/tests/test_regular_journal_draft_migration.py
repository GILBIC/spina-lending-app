from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
PRIMARY_MIGRATION = SQL_ROOT / "0040_add_protected_regular_journal_drafts.sql"
HARDENING_MIGRATION = (
    SQL_ROOT / "0041_harden_regular_journal_manual_post_guard.sql"
)


def migration_sql() -> str:
    return PRIMARY_MIGRATION.read_text(encoding="utf-8")


def hardening_sql() -> str:
    return HARDENING_MIGRATION.read_text(encoding="utf-8")


def test_migrations_are_transactional_and_create_no_live_regular_drafts() -> None:
    sql = migration_sql()
    hardening = hardening_sql()
    for text in (sql, hardening):
        stripped = text.strip()
        assert stripped.startswith("BEGIN;")
        assert stripped.endswith("COMMIT;")

    assert "accounting.regular_journal_draft_preparations" in sql
    assert "accounting.regular_journal_draft_preparation_entries" in sql
    assert "accounting.create_regular_journal_draft_batch" in sql
    assert "false AS regular_journal_posting_enabled" in sql
    assert "false AS automatic_source_posting_enabled" in sql

    # Schema installation only. Creating drafts requires an explicit later
    # function invocation from the authenticated Management API.
    assert "SELECT accounting.create_regular_journal_draft_batch" not in sql
    assert "select accounting.create_regular_journal_draft_batch" not in sql
    assert "create_regular_journal_draft_batch" not in hardening


def test_preparation_permission_is_management_only_and_separate_from_posting() -> None:
    sql = migration_sql()
    assert "accounting.regular_journal.prepare" in sql
    assert "WHERE role.code = 'management'" in sql
    assert "accounting.regular_journal.post" not in sql


def test_source_state_is_serialized_before_draft_validation() -> None:
    sql = migration_sql()
    assert "regular-journal-draft-loan:" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "lending.loan_collection_state" in sql
    assert "lending.collection_transactions" in sql
    assert "IN SHARE MODE" in sql
    assert "LOCK TABLE accounting.fiscal_periods, accounting.accounts IN SHARE MODE" in sql


def test_draft_requires_exact_transaction_identity_period_and_balance() -> None:
    sql = migration_sql()
    assert "'collection:' || p_transaction_id::text" in sql
    assert "'regular_eir_accrual'" in sql
    assert "':fiscal_period:' || fiscal_period_id::text" in sql
    assert "transaction_row.is_voided" in sql
    assert "transaction_row.entry_type NOT IN ('payment', 'advance')" in sql
    assert "posting_date <> transaction_row.collection_date" in sql
    assert "amount <> transaction_row.amount" in sql
    assert "period.status <> 'open'" in sql
    assert "parsed.posting_date NOT BETWEEN period.start_date AND period.end_date" in sql
    assert "total_debit <> entry_amount" in sql
    assert "total_credit <> entry_amount" in sql


def test_draft_enforces_approved_regular_account_patterns() -> None:
    sql = migration_sql()
    assert "accrued_interest_receivable" in sql
    assert "interest_income_regular" in sql
    assert "cash_collector_custody" in sql
    assert "loans_receivable_regular" in sql
    assert "approved 1120/4000 accounting pattern" in sql
    assert "approved 1020/1120/1100 accounting pattern" in sql


def test_source_keys_and_review_tokens_are_unique_and_idempotent() -> None:
    sql = migration_sql()
    assert "review_set_fingerprint ~ '^[0-9a-f]{64}$'" in sql
    assert "bundle_fingerprint ~ '^[0-9a-f]{64}$'" in sql
    assert "source_event_key TEXT NOT NULL UNIQUE" in sql
    assert "transaction_id UUID NOT NULL UNIQUE" in sql
    assert "existing_preparation.review_set_fingerprint" in sql
    assert "RETURN existing_preparation.id" in sql
    assert "already have a journal entry" in sql


def test_system_generated_regular_drafts_are_immutable_and_not_manually_postable() -> None:
    sql = migration_sql()
    assert "guard_regular_system_journal_entry_change" in sql
    assert "guard_regular_system_journal_line_change" in sql
    assert "regular_journal_post_allowed" in sql
    assert "require the protected Regular posting workflow" in sql
    assert "system generated and cannot be edited" in sql
    assert "system generated and immutable" in sql

    # Stage 5D.16 may check the future posting gate but must never enable it.
    assert "set_config('accounting.regular_journal_post_allowed'" not in sql
    assert 'set_config("accounting.regular_journal_post_allowed"' not in sql


def test_manual_general_journal_post_function_is_null_safe_and_source_hardened() -> None:
    sql = hardening_sql()
    assert "entry_row.source_type IS DISTINCT FROM 'manual'" in sql
    assert "entry_row.source_type <> 'manual'" not in sql
    assert (
        "Only a manual draft journal entry can be posted through the manual General Journal workflow."
        in sql
    )
    assert "regular_journal_post_allowed" not in sql


def test_draft_creation_writes_no_entry_number_or_posted_state() -> None:
    sql = migration_sql()
    draft_insert = sql.split(
        "INSERT INTO accounting.journal_entries (", 1
    )[1].split("RETURNING id INTO created_journal_id;", 1)[0]
    assert "'draft'" in draft_insert
    assert "entry_number" not in draft_insert
    assert "posted_by_user_id" not in draft_insert
    assert "posted_at" not in draft_insert
    assert "post_journal_entry(" not in draft_insert
