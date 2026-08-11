from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.regular_cross_period_posting_ready_evidence import (
    REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION,
    RegularCrossPeriodPostingReadyEntryEvidence,
    RegularCrossPeriodPostingReadyEvidenceBundle,
    RegularCrossPeriodPostingReadyJournalLineEvidence,
)
from gilbic_backend.regular_journal_draft_evidence import (
    RegularJournalDraftEvidenceError,
    regular_journal_draft_entries,
    regular_journal_draft_review_fingerprint,
    regular_journal_draft_review_set_fingerprint,
)


TX_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_TX_ID = UUID("22222222-2222-4222-8222-222222222222")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")


def _line(order: int, key: str, side: str, amount: str, label: str):
    return RegularCrossPeriodPostingReadyJournalLineEvidence(
        line_order=order,
        account_system_key=key,
        side=side,
        amount=Decimal(amount),
        label=label,
    )


def _bundle(transaction_id: UUID = TX_ID) -> RegularCrossPeriodPostingReadyEvidenceBundle:
    collection_key = f"collection:{transaction_id}"
    eir = RegularCrossPeriodPostingReadyEntryEvidence(
        sequence_order=1,
        entry_type="eir_accrual_period",
        bundle_entry_key=f"bundle:eir:{transaction_id}",
        sequence_preview_entry_key=f"sequence:eir:{transaction_id}",
        coordinate_preview_key=f"coordinate:eir:{transaction_id}",
        identity_preview_key=f"identity:eir:{transaction_id}",
        upstream_related_source_event_key=f"eir_accrual:{collection_key}",
        source_type="regular_eir_accrual",
        source_reference=f"{transaction_id}:fiscal_period:{JULY_ID}",
        source_event_key=(
            f"eir_accrual:{collection_key}:fiscal_period:{JULY_ID}"
        ),
        related_collection_source_event_key=collection_key,
        recognition_date=date(2026, 7, 31),
        proposed_posting_date=date(2026, 7, 31),
        amount=Decimal("0.01"),
        fiscal_period_id=JULY_ID,
        fiscal_period_label="July 2026",
        fiscal_period_start_date=date(2026, 7, 1),
        fiscal_period_end_date=date(2026, 7, 31),
        fiscal_period_status="open",
        journal_lines=(
            _line(
                1,
                "accrued_interest_receivable",
                "debit",
                "0.01",
                "Effective interest accrued",
            ),
            _line(
                2,
                "interest_income_regular",
                "credit",
                "0.01",
                "Regular effective interest income",
            ),
        ),
        total_debit=Decimal("0.01"),
        total_credit=Decimal("0.01"),
        balanced=True,
    )
    collection = RegularCrossPeriodPostingReadyEntryEvidence(
        sequence_order=2,
        entry_type="collection",
        bundle_entry_key=f"bundle:collection:{transaction_id}",
        sequence_preview_entry_key=f"sequence:collection:{transaction_id}",
        coordinate_preview_key=f"coordinate:collection:{transaction_id}",
        identity_preview_key=f"identity:collection:{transaction_id}",
        upstream_related_source_event_key=collection_key,
        source_type="collection",
        source_reference=str(transaction_id),
        source_event_key=collection_key,
        related_collection_source_event_key=collection_key,
        recognition_date=date(2026, 8, 1),
        proposed_posting_date=date(2026, 8, 1),
        amount=Decimal("1.00"),
        fiscal_period_id=AUGUST_ID,
        fiscal_period_label="August 2026",
        fiscal_period_start_date=date(2026, 8, 1),
        fiscal_period_end_date=date(2026, 8, 31),
        fiscal_period_status="open",
        journal_lines=(
            _line(
                1,
                "cash_collector_custody",
                "debit",
                "1.00",
                "Accepted collection cash",
            ),
            _line(
                2,
                "loans_receivable_regular",
                "credit",
                "1.00",
                "Cash applied to Regular loan component",
            ),
        ),
        total_debit=Decimal("1.00"),
        total_credit=Decimal("1.00"),
        balanced=True,
    )
    return RegularCrossPeriodPostingReadyEvidenceBundle(
        transaction_id=transaction_id,
        collection_source_event_key=collection_key,
        sequence_policy_version="regular_cross_period_accounting_sequence_preview_v1",
        coordinate_policy_version="regular_cross_period_posting_coordinates_v1",
        identity_policy_version="regular_cross_period_posting_identity_v1",
        bundle_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_ready_evidence_complete",
        blocker_code=None,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_coordinate_ready=True,
        posting_identity_ready=True,
        posting_ready_evidence_complete=True,
        message="exact",
        ordered_entries=(eir, collection),
        zero_cent_fiscal_period_ids=(),
    )


def test_review_fingerprint_is_deterministic_and_binds_exact_evidence() -> None:
    bundle = _bundle()
    first = regular_journal_draft_review_fingerprint(bundle)
    second = regular_journal_draft_review_fingerprint(bundle)
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")

    changed_period = replace(
        bundle.ordered_entries[0],
        fiscal_period_label="Changed July",
    )
    changed = replace(
        bundle,
        ordered_entries=(changed_period, bundle.ordered_entries[1]),
    )
    assert regular_journal_draft_review_fingerprint(changed) != first


def test_review_set_fingerprint_binds_transaction_set_and_order() -> None:
    first = _bundle(TX_ID)
    second = _bundle(OTHER_TX_ID)
    token = regular_journal_draft_review_set_fingerprint((first, second))
    assert token == regular_journal_draft_review_set_fingerprint((first, second))
    assert token != regular_journal_draft_review_set_fingerprint((second, first))

    with pytest.raises(RegularJournalDraftEvidenceError):
        regular_journal_draft_review_set_fingerprint((first, first))


def test_draft_entries_preserve_exact_source_period_and_line_evidence() -> None:
    entries = regular_journal_draft_entries(_bundle())
    assert [entry["sequence_order"] for entry in entries] == [1, 2]
    assert [entry["entry_type"] for entry in entries] == [
        "eir_accrual_period",
        "collection",
    ]
    assert entries[0]["source_event_key"] == (
        f"eir_accrual:collection:{TX_ID}:fiscal_period:{JULY_ID}"
    )
    assert entries[1]["source_event_key"] == f"collection:{TX_ID}"
    assert entries[0]["posting_date"] == "2026-07-31"
    assert entries[1]["posting_date"] == "2026-08-01"
    assert entries[0]["journal_lines"][0] == {
        "line_order": 1,
        "account_system_key": "accrued_interest_receivable",
        "side": "debit",
        "amount": "0.01",
        "label": "Effective interest accrued",
    }


def test_blocked_or_tampered_bundle_cannot_generate_draft_evidence() -> None:
    bundle = _bundle()
    blocked = replace(
        bundle,
        posting_ready_evidence_complete=False,
        disposition="regular_cross_period_posting_ready_evidence_blocked",
    )
    with pytest.raises(RegularJournalDraftEvidenceError):
        regular_journal_draft_review_fingerprint(blocked)

    tampered_entry = replace(
        bundle.ordered_entries[0],
        total_credit=Decimal("0.02"),
    )
    tampered = replace(
        bundle,
        ordered_entries=(tampered_entry, bundle.ordered_entries[1]),
    )
    with pytest.raises(RegularJournalDraftEvidenceError):
        regular_journal_draft_entries(tampered)


def test_zero_cent_period_never_receives_a_draft_entry() -> None:
    bundle = _bundle()
    zero_conflict = replace(
        bundle,
        zero_cent_fiscal_period_ids=(JULY_ID,),
    )
    with pytest.raises(RegularJournalDraftEvidenceError):
        regular_journal_draft_entries(zero_conflict)
