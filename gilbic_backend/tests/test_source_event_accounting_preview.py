from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.source_event_accounting_preview import (
    CollectionSourceEvent,
    build_collection_accounting_preview,
    collection_source_event_key,
)


TX_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
JOURNAL_ID = UUID("44444444-4444-4444-8444-444444444444")
REVERSAL_ID = UUID("55555555-5555-4555-8555-555555555555")
CUTOVER = date(2026, 8, 8)


def event(**overrides: object) -> CollectionSourceEvent:
    values: dict[str, object] = {
        "transaction_id": TX_ID,
        "receipt_number": "COL-20260809-000001",
        "client_id": CLIENT_ID,
        "client_code": "C-001",
        "client_name": "Synthetic Borrower",
        "loan_id": LOAN_ID,
        "loan_number": "L-001",
        "loan_type_code": "REGULAR",
        "loan_type_name": "Regular",
        "calculation_mode": "fixed_daily",
        "collection_date": date(2026, 8, 9),
        "accepted_at": datetime(2026, 8, 9, 1, 0, tzinfo=timezone.utc),
        "entry_type": "payment",
        "amount": Decimal("200.00"),
        "is_voided": False,
        "voided_at": None,
    }
    values.update(overrides)
    return CollectionSourceEvent(**values)  # type: ignore[arg-type]


def test_regular_cash_source_is_valid_but_eir_allocation_is_required() -> None:
    preview = build_collection_accounting_preview(event(), cutover_date=CUTOVER)

    assert preview.disposition == "eir_allocation_required"
    assert preview.posting_eligible is False
    assert preview.source_event_key == f"collection:{TX_ID}"
    assert preview.amount == Decimal("200.00")
    assert preview.cash_received_amount == Decimal("200.00")
    assert preview.unallocated_amount == Decimal("0.00")
    assert preview.proposed_lines == ()
    assert "accrued EIR first" in preview.message
    assert "Automatic source posting remains disabled" in preview.message


def test_unallocated_receipt_cash_blocks_loan_source_accounting() -> None:
    preview = build_collection_accounting_preview(
        event(
            amount=Decimal("100.00"),
            cash_received_amount=Decimal("200.00"),
            unallocated_amount=Decimal("100.00"),
        ),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "unallocated_cash_review"
    assert preview.posting_eligible is False
    assert preview.amount == Decimal("100.00")
    assert preview.cash_received_amount == Decimal("200.00")
    assert preview.unallocated_amount == Decimal("100.00")
    assert preview.proposed_lines == ()
    assert "custody/remittance" in preview.message
    assert "do not reduce the loan" in preview.message


def test_fully_unallocated_second_receipt_is_preserved_but_not_loan_posted() -> None:
    preview = build_collection_accounting_preview(
        event(
            amount=Decimal("0.00"),
            cash_received_amount=Decimal("100.00"),
            unallocated_amount=Decimal("100.00"),
        ),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "unallocated_cash_review"
    assert preview.cash_received_amount == Decimal("100.00")
    assert preview.amount == Decimal("0.00")
    assert preview.proposed_lines == ()


def test_receipt_application_mismatch_blocks_accounting() -> None:
    preview = build_collection_accounting_preview(
        event(
            amount=Decimal("100.00"),
            cash_received_amount=Decimal("250.00"),
            unallocated_amount=Decimal("100.00"),
        ),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "receipt_application_mismatch"
    assert preview.posting_eligible is False
    assert preview.proposed_lines == ()


def test_7x7_cash_source_never_assumes_full_credit_to_principal() -> None:
    preview = build_collection_accounting_preview(
        event(
            loan_type_code="7X7",
            loan_type_name="7x7",
            calculation_mode="seven_by_seven",
            amount=Decimal("50.00"),
        ),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "eir_allocation_required"
    assert preview.proposed_lines == ()
    assert "loan component and accrued effective interest" in preview.message


def test_advance_is_cash_source_but_still_requires_eir_allocation() -> None:
    preview = build_collection_accounting_preview(
        event(entry_type="advance", amount=Decimal("600.00")),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "eir_allocation_required"
    assert preview.amount == Decimal("600.00")
    assert preview.proposed_lines == ()


def test_pass_is_non_cash_and_never_proposes_a_journal() -> None:
    preview = build_collection_accounting_preview(
        event(entry_type="pass", amount=Decimal("0.00")),
        cutover_date=CUTOVER,
    )

    assert preview.disposition == "informational_only"
    assert preview.proposed_lines == ()
    assert preview.posting_eligible is False


def test_pass_with_existing_journal_is_flagged_as_inconsistent() -> None:
    preview = build_collection_accounting_preview(
        event(
            entry_type="pass",
            amount=Decimal("0.00"),
            journal_entry_id=JOURNAL_ID,
            journal_status="draft",
        ),
        cutover_date=CUTOVER,
    )
    assert preview.disposition == "unexpected_journal"


@pytest.mark.parametrize(
    ("collection_date", "expected"),
    [
        (date(2026, 8, 7), "pre_cutover"),
        (date(2026, 8, 8), "cutover_date_review"),
        (date(2026, 8, 9), "eir_allocation_required"),
    ],
)
def test_cutover_boundary_never_double_counts(collection_date: date, expected: str) -> None:
    preview = build_collection_accounting_preview(
        event(collection_date=collection_date),
        cutover_date=CUTOVER,
    )
    assert preview.disposition == expected
    assert preview.proposed_lines == ()


def test_missing_cutover_blocks_mapping() -> None:
    preview = build_collection_accounting_preview(event(), cutover_date=None)
    assert preview.disposition == "cutover_required"
    assert preview.proposed_lines == ()


def test_custom_loan_mode_requires_policy_instead_of_assuming_regular() -> None:
    preview = build_collection_accounting_preview(
        event(calculation_mode="custom", loan_type_code="SPECIAL"),
        cutover_date=CUTOVER,
    )
    assert preview.disposition == "policy_review"
    assert preview.proposed_lines == ()


def test_voided_before_accounting_creates_no_entry_or_reversal() -> None:
    preview = build_collection_accounting_preview(
        event(
            is_voided=True,
            voided_at=datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc),
        ),
        cutover_date=CUTOVER,
    )
    assert preview.disposition == "voided_before_accounting"
    assert preview.proposed_lines == ()


def test_voided_posted_collection_requires_controlled_reversal() -> None:
    preview = build_collection_accounting_preview(
        event(
            is_voided=True,
            voided_at=datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc),
            journal_entry_id=JOURNAL_ID,
            journal_status="posted",
            journal_entry_number="JE-202608-00000001",
        ),
        cutover_date=CUTOVER,
    )
    assert preview.disposition == "reversal_required"
    assert preview.proposed_lines == ()
    assert "controlled reversal" in preview.message


def test_voided_posted_collection_reports_existing_reversal_state() -> None:
    draft = build_collection_accounting_preview(
        event(
            is_voided=True,
            journal_entry_id=JOURNAL_ID,
            journal_status="posted",
            reversal_entry_id=REVERSAL_ID,
            reversal_status="draft",
        ),
        cutover_date=CUTOVER,
    )
    posted = build_collection_accounting_preview(
        event(
            is_voided=True,
            journal_entry_id=JOURNAL_ID,
            journal_status="posted",
            reversal_entry_id=REVERSAL_ID,
            reversal_status="posted",
            reversal_entry_number="JE-202608-00000002",
        ),
        cutover_date=CUTOVER,
    )
    assert draft.disposition == "reversal_draft_exists"
    assert posted.disposition == "reversed"


def test_existing_source_journal_prevents_duplicate_source_event() -> None:
    draft = build_collection_accounting_preview(
        event(journal_entry_id=JOURNAL_ID, journal_status="draft"),
        cutover_date=CUTOVER,
    )
    posted = build_collection_accounting_preview(
        event(
            journal_entry_id=JOURNAL_ID,
            journal_status="posted",
            journal_entry_number="JE-202608-00000001",
        ),
        cutover_date=CUTOVER,
    )
    assert draft.disposition == "draft_exists"
    assert posted.disposition == "already_posted"
    assert draft.source_event_key == posted.source_event_key
    assert draft.proposed_lines == ()
    assert posted.proposed_lines == ()


def test_source_event_key_is_deterministic() -> None:
    assert collection_source_event_key(TX_ID) == collection_source_event_key(TX_ID)
    assert collection_source_event_key(TX_ID) == f"collection:{TX_ID}"
