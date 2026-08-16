from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from gilbic_backend.source_event_accounting_preview import CollectionSourceEvent
from gilbic_backend.source_event_accounting_repository import (
    decode_source_event_cursor,
    encode_source_event_cursor,
)


REPOSITORY_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "gilbic_backend"
    / "source_event_accounting_repository.py"
)


def _event() -> CollectionSourceEvent:
    return CollectionSourceEvent(
        transaction_id=UUID("11111111-1111-4111-8111-111111111111"),
        receipt_number="COL-1",
        client_id=UUID("22222222-2222-4222-8222-222222222222"),
        client_code="C-1",
        client_name="Synthetic Borrower",
        loan_id=UUID("33333333-3333-4333-8333-333333333333"),
        loan_number="L-1",
        loan_type_code="REGULAR",
        loan_type_name="Regular",
        calculation_mode="fixed_daily",
        collection_date=date(2026, 8, 9),
        accepted_at=datetime(2026, 8, 9, 4, 5, 6, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("200.00"),
        is_voided=False,
        voided_at=None,
    )


def test_cursor_round_trip_preserves_full_keyset_boundary() -> None:
    event = _event()
    cursor = decode_source_event_cursor(encode_source_event_cursor(event))
    assert cursor.collection_date == event.collection_date
    assert cursor.accepted_at == event.accepted_at
    assert cursor.transaction_id == event.transaction_id


@pytest.mark.parametrize("value", ["", "not-base64!!!", "bm90LWpzb24", "e30"])
def test_malformed_cursor_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        decode_source_event_cursor(value)


def test_repository_uses_complete_keyset_pagination_and_limit_plus_one() -> None:
    source = REPOSITORY_SOURCE.read_text(encoding="utf-8")
    assert "safe_limit + 1" in source
    assert "transaction.collection_date," in source
    assert "transaction.accepted_at," in source
    assert "transaction.id" in source
    assert ") < (%s::date, %s::timestamptz, %s::uuid)" in source
    assert "has_more = len(loaded) > safe_limit" in source
    assert "encode_source_event_cursor(events[-1])" in source


def test_repository_separates_receipt_cash_from_loan_applied_amount() -> None:
    source = REPOSITORY_SOURCE.read_text(encoding="utf-8")
    assert "transaction.applied_amount as amount" in source
    assert "transaction.amount as cash_received_amount" in source
    assert "transaction.unallocated_amount" in source
    assert "cash_received_amount=Decimal(row[\"cash_received_amount\"] or 0)" in source
    assert "unallocated_amount=Decimal(row[\"unallocated_amount\"] or 0)" in source


def test_repository_uses_same_current_workbook_rule_as_opening_workflow() -> None:
    source = REPOSITORY_SOURCE.read_text(encoding="utf-8")
    assert "order by workbook.created_at desc" in source
    assert "order by workbook.cutover_date desc" not in source


def test_repository_is_read_only() -> None:
    source = REPOSITORY_SOURCE.read_text(encoding="utf-8").lower()
    assert "insert into" not in source
    assert "update lending." not in source
    assert "delete from" not in source
