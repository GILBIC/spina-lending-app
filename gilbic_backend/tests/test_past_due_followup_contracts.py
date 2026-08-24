from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from gilbic_backend.past_due_followup_contracts import (
    PastDueReasonBody,
    PastDueReasonCode,
)


def test_other_reason_requires_explanation() -> None:
    with pytest.raises(ValidationError) as captured:
        PastDueReasonBody(reason_code=PastDueReasonCode.OTHER, note="")

    assert "requires a short explanation" in str(captured.value)


def test_promise_reason_requires_date_and_amount() -> None:
    with pytest.raises(ValidationError) as captured:
        PastDueReasonBody(
            reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
            note="Will pay after salary",
        )

    assert "requires a promised payment date" in str(captured.value)


def test_promise_reason_accepts_partial_promised_amount() -> None:
    reason = PastDueReasonBody(
        reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
        note="Will pay part on Friday",
        promised_payment_date=date(2026, 8, 28),
        promised_amount=Decimal("200.00"),
    )

    assert reason.promised_payment_date == date(2026, 8, 28)
    assert reason.promised_amount == Decimal("200.00")


def test_non_promise_reason_rejects_promise_fields() -> None:
    with pytest.raises(ValidationError) as captured:
        PastDueReasonBody(
            reason_code=PastDueReasonCode.NO_CASH,
            promised_payment_date=date(2026, 8, 28),
            promised_amount=Decimal("100.00"),
        )

    assert "only valid for Promised to pay later" in str(captured.value)
