from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
POSTING = (PACKAGE / "seven_by_seven_collection_posting.py").read_text(encoding="utf-8")
SCHEDULE_ALLOCATION = (PACKAGE / "seven_by_seven_schedule_allocation.py").read_text(
    encoding="utf-8"
)


def test_verified_7x7_payment_plans_and_persists_installment_evidence() -> None:
    assert "plan_verified_seven_by_seven_scheduled_payment" in POSTING
    assert "store_verified_seven_by_seven_scheduled_payment_allocations" in POSTING
    assert "loan_installment_payment_allocations" in SCHEDULE_ALLOCATION
    assert "'oldest_due_first'" in SCHEDULE_ALLOCATION


def test_normal_7x7_payment_never_auto_advances_true_extra() -> None:
    assert "SevenBySevenExtraAllocationChoiceRequired" in SCHEDULE_ALLOCATION
    assert "beyond Past Due and Due Today" in SCHEDULE_ALLOCATION
    assert "effective_due_date <= collection_date" in SCHEDULE_ALLOCATION


def test_same_day_7x7_cash_receipts_are_not_rejected_by_date_guard() -> None:
    assert "if entry_type is not CollectionEntryType.PASS:" in POSTING
    assert "on conflict (loan_id, covered_date) do nothing" in POSTING
    assert "order by collection_date, accepted_at, id" in POSTING


def test_advance_schedule_allocation_is_not_claimed_complete_yet() -> None:
    assert '"advance_integration_pending"' in POSTING
