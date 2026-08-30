from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "ecl_a5_accounting_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "ecl_a5_accounting_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_a5_management_api_is_wired_and_permission_scoped() -> None:
    assert "create_ecl_a5_accounting_router" in MAIN
    assert "app.include_router(create_ecl_a5_accounting_router())" in MAIN
    for permission in (
        'REMEASUREMENT_PERMISSION = "accounting.ecl.remeasurement.post"',
        'WRITEOFF_PERMISSION = "accounting.ecl.writeoff.post"',
        'RECOVERY_REVIEW_PERMISSION = "accounting.ecl.recovery.review"',
        'RECOVERY_POST_PERMISSION = "accounting.ecl.recovery.post"',
    ):
        assert permission in API
    for route in (
        "/ecl-a5/measurements/{measurement_id}/remeasure",
        "/ecl-a5/loans/{loan_id}/writeoff",
        "/ecl-a5/loans/{loan_id}/recovery-review",
        "/ecl-a5/reviews/{credit_risk_review_id}/recovery",
    ):
        assert route in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API


def test_a5_mobile_queue_exposes_complete_server_derived_action_coordinates() -> None:
    for field in (
        '"recovery_candidate_transaction_id"',
        '"recovery_candidate_amount"',
        '"recovery_candidate_collection_date"',
        '"posting_date"',
        '"fiscal_period_id"',
        '"credit_loss_expense_account_id"',
        '"allowance_account_id"',
        '"cash_account_id"',
    ):
        assert field in API
    for authority in (
        "transaction_row.accepted_at > writeoff.posted_at",
        "NOT transaction_row.is_voided",
        "transaction_row.entry_type IN ('payment', 'advance')",
        "accounting.regular_journal_posting_entries",
        "accounting.seven_by_seven_journal_postings",
        "accounting.ecl_post_writeoff_recovery_review_provenance",
        "accounting.ecl_post_writeoff_recoveries",
        "recovery_review_required",
        "accounting.fiscal_periods",
        "credit_loss_expense",
        "allowance_expected_credit_loss",
        "cash_collector_custody",
    ):
        assert authority in REPOSITORY


def test_a5_requests_are_strict_and_require_exact_confirmation() -> None:
    assert 'ConfigDict(extra="forbid")' in API
    for field in (
        "review_token",
        "expected_calculation_digest",
        "expected_prior_allowance",
        "expected_target_allowance",
        "expected_credit_risk_review_id",
        "expected_measurement_id",
        "expected_loan_component",
        "expected_accrued_interest_component",
        "expected_gross_carrying_amount",
        "expected_allowance_balance",
        "expected_recovery_transaction_id",
        "expected_recovery_amount",
        "evidence_reference",
        "review_note",
        "expected_posting_date",
        "expected_fiscal_period_id",
        "expected_cash_account_id",
        "expected_credit_loss_expense_account_id",
        "expected_allowance_account_id",
    ):
        assert field in API
    assert "exact currency-cent precision" in API
    assert "Gross carrying amount must equal the exact loan plus accrued-interest components" in API
    assert "V1 full write-off requires exact allowance equal to gross carrying amount" in API


def test_a5_repository_exposes_only_protected_database_functions() -> None:
    for function in (
        "accounting.post_ecl_allowance_remeasurement",
        "accounting.post_ecl_full_writeoff",
        "accounting.review_ecl_post_writeoff_recovery",
        "accounting.post_ecl_post_writeoff_recovery",
    ):
        assert function in REPOSITORY
    assert 'REMEASUREMENT_POLICY = "ecl_allowance_remeasurement_posting_v1"' in REPOSITORY
    assert 'WRITEOFF_POLICY = "ecl_full_writeoff_posting_v1"' in REPOSITORY
    assert 'RECOVERY_REVIEW_POLICY = "ecl_post_writeoff_recovery_evidence_review_v1"' in REPOSITORY
    assert 'RECOVERY_POLICY = "ecl_post_writeoff_recovery_posting_v1"' in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "insert into accounting.journal_lines" not in REPOSITORY.lower()


def test_a5_api_preserves_explicit_management_only_accounting_boundary() -> None:
    assert '"automatic_source_posting": False' in API
    assert "Write-off support alone never derecognizes a loan" in API
    assert "post-write-off recovery never recreates a receivable or allowance" in API
    assert "automatic source posting remains disabled" in API
