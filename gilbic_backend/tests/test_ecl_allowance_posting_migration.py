from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0077_add_protected_ecl_allowance_posting.sql").read_text(
    encoding="utf-8"
)


def test_0077_adds_protected_prepare_and_post_boundaries() -> None:
    lower = SQL.lower()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "accounting.ecl.allowance.prepare" in lower
    assert "accounting.ecl.allowance.post" in lower
    assert "create table if not exists accounting.ecl_allowance_draft_preparations" in lower
    assert "create table if not exists accounting.ecl_allowance_postings" in lower
    assert "create table if not exists accounting.ecl_allowance_posting_lines" in lower
    assert "prepare_initial_ecl_allowance_journal" in lower
    assert "post_initial_ecl_allowance_journal" in lower
    assert "ecl_allowance_initial_journal_draft_v1" in lower
    assert "ecl_allowance_initial_journal_posting_v1" in lower


def test_0077_ties_posting_to_exact_current_a3_measurement() -> None:
    lower = SQL.lower()
    assert "measurement_status <> 'measured_read_only'" in lower
    assert "queue.measurement_id is distinct from measurement.id" in lower
    assert "queue.authoritative_ecl_amount is distinct from measurement.ecl_amount" in lower
    assert "measurement.calculation_digest <> normalized_digest" in lower
    assert "current authoritative measurement" in lower
    assert "exact quantitative ecl source measurement" in lower
    assert "measurement_forward_evidence_current is distinct from true" in lower


def test_0077_revalidates_period_accounts_amount_journal_and_prior_allowance() -> None:
    lower = SQL.lower()
    assert "period_row.status <> 'open'" in lower
    assert "system_key <> 'credit_loss_expense'" in lower
    assert "expense_account.code <> '5000'" in lower
    assert "system_key <> 'allowance_expected_credit_loss'" in lower
    assert "allowance_account.code <> '1190'" in lower
    assert "journal_row.source_type <> 'ecl_allowance'" in lower
    assert "journal_row.source_event_key <> prepared.source_event_key" in lower
    assert "current_allowance <> prepared.prior_allowance_balance" in lower
    assert "prior allowance balance 0.00" in lower
    assert "a5 remeasurement accounting" in lower


def test_0077_blocks_generic_1190_and_manual_reversal_bypass() -> None:
    lower = SQL.lower()
    assert "guard_ecl_allowance_journal_line_change" in lower
    assert "account 1190 allowance for expected credit loss can only be changed" in lower
    assert "ecl_allowance_journal_line_write_allowed" in lower
    assert "posted protected ecl allowance journals cannot be reversed through the manual general journal" in lower
    assert "ecl_allowance_reversal_allowed" in lower
    assert "protected ecl allowance journal drafts require the protected allowance posting workflow" in lower


def test_0077_is_immutable_idempotent_and_atomic_audit_ready() -> None:
    lower = SQL.lower()
    assert "guard_ecl_allowance_preparation_record_write" in lower
    assert "guard_ecl_allowance_posting_audit_write" in lower
    assert "existing protected ecl allowance posting audit" in lower
    assert "return existing.id" in lower
    # Journal posting occurs before immutable posting-audit insertion inside one
    # PostgreSQL function transaction, so a forced audit-trigger failure rolls it back.
    assert lower.index("accounting.post_journal_entry(") < lower.index(
        "insert into accounting.ecl_allowance_postings"
    )
    assert "insert into accounting.ecl_allowance_posting_lines" in lower


def test_0077_keeps_automatic_source_posting_off() -> None:
    assert "true AS account_1190_posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL
    assert "'automatic_source_posting', false" in SQL
    assert "automatic_source_posting', true" not in SQL
