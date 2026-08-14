from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0082_add_v1_tax_evidence_readiness.sql").read_text(
    encoding="utf-8"
)
POLICY = (
    ROOT.parent / "docs" / "accounting" / "v1-tax-accounting-policy.md"
).read_text(encoding="utf-8")
LOWER = SQL.lower()
POLICY_LOWER = POLICY.lower()


def test_v1_tax_evidence_migration_is_transactional_management_only_and_readiness_only() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.rule_evidence.record",
        "accounting.tax.dst_evidence.record",
        "accounting.tax.percentage_evidence.record",
    ):
        assert permission in SQL
    assert "require_v1_tax_management_actor" in LOWER
    assert "where role.code = 'management'" in LOWER
    assert "false as tax_posting_enabled" in LOWER
    assert "false as automatic_source_posting" in LOWER
    assert "insert into accounting.journal_entries" not in LOWER
    assert "insert into accounting.journal_lines" not in LOWER
    assert "post_journal_entry" not in LOWER


def test_v1_tax_rule_evidence_is_versioned_immutable_and_evidence_backed() -> None:
    for relation in (
        "accounting.v1_tax_rule_evidence",
        "accounting.v1_dst_evidence",
        "accounting.v1_percentage_tax_evidence",
    ):
        assert relation in LOWER
    assert "guard_v1_tax_evidence_write" in LOWER
    assert "immutable" in LOWER
    assert "supersedes_rule_id" in LOWER
    assert "supersedes_evidence_id" in LOWER
    assert "evidence_digest" in LOWER
    assert "management_rationale" in LOWER
    assert "legal_source" in LOWER
    assert "retained_source_reference" in LOWER
    assert "taxable" in LOWER and "exempt" in LOWER


def test_dst_evidence_uses_exact_protected_loan_disbursement_and_term_coordinates() -> None:
    assert "record_v1_dst_evidence" in LOWER
    assert "lending.loan_disbursement_events" in LOWER
    assert "event_row.is_voided" in LOWER
    assert "event_row.principal_snapshot <> loan_row.principal" in LOWER
    assert "actual_term_days := loan_row.due_date - loan_row.date_released" in LOWER
    assert "issue_price <> event_row.principal_snapshot" in LOWER
    assert "proration_days := case when actual_term_days < 365 then actual_term_days else 365 end" in LOWER
    assert "issue_price * rule_row.rate * proration_days::numeric / 365::numeric" in LOWER
    assert "instrument_digest" in LOWER
    assert "calculation_digest" in LOWER


def test_percentage_tax_evidence_never_substitutes_pfrs_eir_as_tax_base() -> None:
    assert "record_v1_percentage_tax_evidence" in LOWER
    assert "taxable_lending_receipt_amount" in LOWER
    assert "principal_receipt_amount" in LOWER
    assert "source_cash_amount = taxable_lending_receipt_amount + principal_receipt_amount" in LOWER
    assert "regular_journal_posting_entries" in LOWER
    assert "seven_by_seven_journal_postings" in LOWER
    assert "transaction_row.is_voided" in LOWER
    assert "taxable_receipt * rule_row.rate" in LOWER

    # Tax evidence must not derive its base from PFRS/EIR accounting coordinates.
    for forbidden in (
        "accounting_eir_interest_received",
        "interest_income_regular",
        "interest_income_7x7",
        "accrued_interest_receivable",
        "account.code = '4000'",
        "account.code = '4010'",
        "account.code = '1120'",
    ):
        assert forbidden not in LOWER


def test_tax_policy_explicitly_separates_eir_from_tax_basis_and_keeps_live_posting_off() -> None:
    assert "pfrs eir is not automatically the tax gross-receipts base" in POLICY_LOWER
    assert "must **not** calculate percentage/gross-receipts tax" in POLICY_LOWER
    assert "automatic_source_posting=false" in POLICY_LOWER
    assert "evidence/readiness only" in POLICY_LOWER
    assert "actual tax accounting may post only" in POLICY_LOWER
