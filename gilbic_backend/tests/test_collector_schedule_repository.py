from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import gilbic_backend.collector_schedule_repository as schedule_repository
from gilbic_backend.collector_schedule_repository import (
    PostgresCollectorScheduleRepository,
)


COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
SCHEDULE_ID = UUID("44444444-4444-4444-8444-444444444444")


class FakeCursor:
    def __init__(self) -> None:
        self._one = None
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()) -> None:
        normalized = " ".join(sql.split())
        if "from lending.loans loan" in normalized:
            self._one = {
                "loan_id": LOAN_ID,
                "loan_number": "REG-1001",
                "client_id": CLIENT_ID,
                "client_name": "Borrower One",
                "loan_type": "Regular",
                "calculation_mode": "fixed_total",
                "schedule_id": SCHEDULE_ID,
                "schedule_version": 1,
                "payment_frequency": "daily",
                "contract_reference": "SIGNED-REG-1001",
                "settings": {},
                "registration_id": UUID("55555555-5555-4555-8555-555555555555"),
                "active_borrower_extension_slots": 1,
            }
            self._many = []
            return
        if "from lending.loan_contract_installments_operational installment" in normalized:
            self._one = None
            self._many = [
                self._installment(1, date(2026, 8, 25), date(2026, 8, 26)),
                self._installment(2, date(2026, 8, 26), date(2026, 8, 27)),
                self._installment(3, date(2026, 8, 27), date(2026, 8, 28)),
            ]
            return
        if "from lending.loan_schedule_adjustments adjustment" in normalized:
            self._one = None
            self._many = []
            return
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)

    @staticmethod
    def _installment(
        number: int,
        contractual_due_date: date,
        effective_due_date: date,
    ) -> dict[str, object]:
        return {
            "id": number,
            "installment_number": number,
            "contractual_due_date": contractual_due_date,
            "effective_due_date": effective_due_date,
            "contractual_amount": Decimal("200.00"),
            "principal_component": None,
            "interest_component": None,
            "paid_amount": Decimal("0.00"),
            "prepaid_amount": Decimal("0.00"),
            "principal_reduction_amount": Decimal("0.00"),
            "past_due_reason_code": "",
            "past_due_reason_note": "",
            "promised_for_date": None,
            "promise_remaining_amount": Decimal("0.00"),
            "promise_status": "",
        }


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *, row_factory=None):
        return self.cursor_instance


def test_persisted_borrower_shift_is_authoritative_without_reader_reprojection(
    monkeypatch,
) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(schedule_repository, "open_connection", lambda: connection)

    schedule = PostgresCollectorScheduleRepository().get_schedule(
        collector_user_id=COLLECTOR_ID,
        loan_id=LOAN_ID,
        as_of_date=date(2026, 8, 26),
    )

    installments = [row for row in schedule.rows if row.kind == "installment"]
    assert [(row.schedule_date, row.status) for row in installments] == [
        (date(2026, 8, 26), "Due Today"),
        (date(2026, 8, 27), "Scheduled"),
        (date(2026, 8, 28), "Scheduled"),
    ]
    assert schedule.past_due_count == 0
    assert schedule.past_due_amount == Decimal("0.00")
    assert schedule.schedule_extension_slots == 1
    assert schedule.base_maturity == date(2026, 8, 27)
    assert schedule.updated_maturity == date(2026, 8, 28)
    assert schedule.maturity_projection_status == "extended"
