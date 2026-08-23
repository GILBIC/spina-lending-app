from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.combined_collection_api import (
    CombinedPaymentLeg,
    CombinedPaymentRequest,
    _validate_regular_plus_7x7,
)
from spina_mobile_collections.service import CollectionRejected


CLIENT_ID = UUID("11111111-1111-4111-8111-111111111111")
REGULAR_LOAN_ID = UUID("22222222-2222-4222-8222-222222222222")
SEVEN_LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, *_args, **_kwargs):
        return self

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, **_kwargs):
        return _Cursor(self._rows)


def _body() -> CombinedPaymentRequest:
    return CombinedPaymentRequest(
        client_transaction_id=UUID("44444444-4444-4444-8444-444444444444"),
        client_id=CLIENT_ID,
        collection_date=date(2026, 8, 23),
        recorded_at=datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc),
        device_id="collector-phone",
        device_sequence=1,
        legs=[
            CombinedPaymentLeg(
                route_entry_id=REGULAR_LOAN_ID,
                loan_id=REGULAR_LOAN_ID,
                route_revision=f"loan:{REGULAR_LOAN_ID}:v1",
                amount=Decimal("200.00"),
            ),
            CombinedPaymentLeg(
                route_entry_id=SEVEN_LOAN_ID,
                loan_id=SEVEN_LOAN_ID,
                route_revision=f"loan:{SEVEN_LOAN_ID}:v1",
                amount=Decimal("35.00"),
            ),
        ],
    )


def _rows(first_mode: str, second_mode: str):
    return [
        {
            "id": REGULAR_LOAN_ID,
            "client_id": CLIENT_ID,
            "status": "active",
            "calculation_mode": first_mode,
        },
        {
            "id": SEVEN_LOAN_ID,
            "client_id": CLIENT_ID,
            "status": "active",
            "calculation_mode": second_mode,
        },
    ]


def test_exact_fixed_daily_plus_7x7_is_allowed() -> None:
    _validate_regular_plus_7x7(
        _Connection(_rows("fixed_daily", "seven_by_seven")),
        _body(),
    )


def test_custom_plus_7x7_fails_closed() -> None:
    with pytest.raises(CollectionRejected) as caught:
        _validate_regular_plus_7x7(
            _Connection(_rows("custom", "seven_by_seven")),
            _body(),
        )

    assert caught.value.code == "combined_regular_7x7_required"


def test_two_non_7x7_loans_fail_closed() -> None:
    with pytest.raises(CollectionRejected) as caught:
        _validate_regular_plus_7x7(
            _Connection(_rows("fixed_daily", "custom")),
            _body(),
        )

    assert caught.value.code == "combined_regular_7x7_required"
