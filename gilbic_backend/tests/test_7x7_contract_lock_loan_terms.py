from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

import gilbic_backend.contract_schedule_registration_service as registration_service
from gilbic_backend.contract_schedule_service import ContractScheduleConflict
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


class RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.statements.append((" ".join(query.split()), params))


def _signed_rows():
    release_date = date(2098, 1, 1)
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=release_date + timedelta(days=1),
    )
    assert len(rows) == 104
    return release_date, rows


def test_unconfirmed_7x7_contract_lock_does_not_sync_loan_terms(monkeypatch) -> None:
    loan_id = uuid4()
    actor_id = uuid4()
    release_date, rows = _signed_rows()
    cursor = RecordingCursor()
    store_called = False

    def fake_store_contract_schedule(*args, **kwargs):
        nonlocal store_called
        store_called = True
        return uuid4()

    monkeypatch.setattr(
        registration_service,
        "store_contract_schedule",
        fake_store_contract_schedule,
    )

    with pytest.raises(ContractScheduleConflict):
        registration_service.register_verified_contract_schedule(
            cursor,
            loan_id=loan_id,
            payment_frequency="daily",
            contract_reference="P6-UNCONFIRMED",
            contract_signed_date=release_date,
            effective_from=release_date,
            grace_days=0,
            installments=rows,
            evidence_basis="signed_contract",
            evidence_reference="P6-EVIDENCE-UNCONFIRMED",
            verification_note="Unconfirmed contract-lock regression proof.",
            verified_by_user_id=actor_id,
            agreed_daily_payment=Decimal("50.00"),
            confirmed=False,
        )

    assert store_called is False
    assert cursor.statements == []


def test_confirmed_7x7_contract_lock_syncs_daily_amount_and_signed_maturity(
    monkeypatch,
) -> None:
    loan_id = uuid4()
    actor_id = uuid4()
    schedule_id = uuid4()
    release_date, rows = _signed_rows()
    cursor = RecordingCursor()

    monkeypatch.setattr(
        registration_service,
        "store_contract_schedule",
        lambda *args, **kwargs: schedule_id,
    )

    stored_schedule_id = registration_service.register_verified_contract_schedule(
        cursor,
        loan_id=loan_id,
        payment_frequency="daily",
        contract_reference="P6-CONFIRMED",
        contract_signed_date=release_date,
        effective_from=release_date,
        grace_days=0,
        installments=rows,
        evidence_basis="signed_contract",
        evidence_reference="P6-EVIDENCE-CONFIRMED",
        verification_note="Borrower accepted the agreed 50 peso daily payment.",
        verified_by_user_id=actor_id,
        agreed_daily_payment=Decimal("50.00"),
        confirmed=True,
    )

    assert stored_schedule_id == schedule_id
    loan_updates = [
        (statement, params)
        for statement, params in cursor.statements
        if statement.lower().startswith("update lending.loans")
    ]
    assert loan_updates == [
        (
            "update lending.loans set daily_amount = %s, due_date = %s where id = %s",
            (Decimal("50.00"), rows[-1].due_date, loan_id),
        )
    ]
