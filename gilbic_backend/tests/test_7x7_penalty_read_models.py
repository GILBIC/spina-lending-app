from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import gilbic_backend.client_loan_api as client_api
import gilbic_backend.client_loan_repository as client_repository
import gilbic_backend.collector_schedule_api as collector_api
import gilbic_backend.collector_schedule_repository as collector_repository
from gilbic_backend.client_loan_repository import PostgresClientLoanRepository
from gilbic_backend.collector_schedule_repository import PostgresCollectorScheduleRepository


COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
SCHEDULE_ID = UUID("55555555-5555-4555-8555-555555555555")
REGISTRATION_ID = UUID("66666666-6666-4666-8666-666666666666")
AS_OF_DATE = date(2026, 8, 27)


class FakeCursor:
    def __init__(self, *, calculation_mode: str) -> None:
        self.calculation_mode = calculation_mode
        self._one = None
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()) -> None:
        normalized = " ".join(sql.split())
        if normalized.startswith("select id from lending.clients where user_id"):
            self._one = {"id": CLIENT_ID}
            self._many = []
            return
        if "from lending.loans loan join lending.clients client" in normalized:
            self._one = self._loan_row()
            self._many = []
            return
        if "from lending.clients client join lending.loans loan" in normalized:
            self._one = self._loan_row()
            self._many = []
            return
        if "from lending.loan_contract_installments_operational installment" in normalized:
            self._one = None
            self._many = [
                self._installment(
                    number=1,
                    due=date(2026, 8, 25),
                    paid=Decimal("10.00"),
                ),
                self._installment(
                    number=2,
                    due=date(2026, 8, 26),
                    paid=Decimal("0.00"),
                ),
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

    def _loan_row(self) -> dict[str, object]:
        loan_type = "7x7" if self.calculation_mode == "seven_by_seven" else "Regular"
        return {
            "loan_id": LOAN_ID,
            "loan_number": "LN-READ-001",
            "client_id": CLIENT_ID,
            "client_name": "Borrower One",
            "loan_type": loan_type,
            "calculation_mode": self.calculation_mode,
            "schedule_id": SCHEDULE_ID,
            "schedule_version": 4,
            "payment_frequency": "daily",
            "contract_reference": "SIGNED-READ-001",
            "settings": {},
            "registration_id": REGISTRATION_ID,
            "active_borrower_extension_slots": 0,
        }

    @staticmethod
    def _installment(*, number: int, due: date, paid: Decimal) -> dict[str, object]:
        return {
            "id": number,
            "installment_number": number,
            "contractual_due_date": due,
            "effective_due_date": due,
            "contractual_amount": Decimal("50.00"),
            "principal_component": Decimal("30.00"),
            "interest_component": Decimal("20.00"),
            "paid_amount": paid,
            "prepaid_amount": Decimal("0.00"),
            "principal_reduction_amount": Decimal("0.00"),
            "past_due_reason_code": "",
            "past_due_reason_note": "",
            "promised_for_date": None,
            "promise_remaining_amount": Decimal("0.00"),
            "promise_status": "",
        }


class FakeConnection:
    def __init__(self, *, calculation_mode: str) -> None:
        self.calculation_mode = calculation_mode

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *, row_factory=None):
        return FakeCursor(calculation_mode=self.calculation_mode)


def _penalty_state(*, status: str = "projected") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        projected_penalty=Decimal("5.13") if status == "projected" else Decimal("0.00"),
        assessed_penalty_balance=Decimal("1.25"),
        penalty_base=Decimal("89.00"),
        remaining_cost_headroom=Decimal("4993.62"),
        management_review_required_reason=(
            "" if status != "management_review_required" else "Exact signed authority is missing."
        ),
    )


def _assert_projected_read_model(schedule) -> None:
    assert schedule.penalty_status == "projected"
    assert schedule.projected_penalty == Decimal("5.13")
    assert schedule.assessed_penalty_balance == Decimal("1.25")
    assert schedule.penalty_base == Decimal("89.00")
    assert schedule.remaining_cost_headroom == Decimal("4993.62")
    assert schedule.exact_payoff_total == Decimal("96.38")
    assert schedule.management_review_required_reason == ""
    assert schedule.base_maturity == date(2026, 8, 26)
    assert schedule.updated_maturity == date(2026, 8, 26)


def _assert_neutral_regular_read_model(schedule) -> None:
    assert schedule.penalty_status == "not_applicable"
    assert schedule.projected_penalty == Decimal("0.00")
    assert schedule.assessed_penalty_balance == Decimal("0.00")
    assert schedule.penalty_base == Decimal("0.00")
    assert schedule.remaining_cost_headroom == Decimal("0.00")
    assert schedule.exact_payoff_total == Decimal("0.00")
    assert schedule.management_review_required_reason == ""


def test_collector_repository_uses_shared_penalty_coordinator_for_7x7(monkeypatch) -> None:
    connection = FakeConnection(calculation_mode="seven_by_seven")
    calls: list[tuple[UUID, date]] = []

    def project(cursor, *, loan_id: UUID, as_of_date: date):
        calls.append((loan_id, as_of_date))
        return _penalty_state()

    monkeypatch.setattr(collector_repository, "open_connection", lambda: connection)
    monkeypatch.setattr(
        collector_repository,
        "project_verified_seven_by_seven_penalty_state",
        project,
        raising=False,
    )

    schedule = PostgresCollectorScheduleRepository().get_schedule(
        collector_user_id=COLLECTOR_ID,
        loan_id=LOAN_ID,
        as_of_date=AS_OF_DATE,
    )

    assert calls == [(LOAN_ID, AS_OF_DATE)]
    _assert_projected_read_model(schedule)

    collector_payload = collector_api._schedule_payload(schedule)
    client_payload = client_api._client_schedule_payload(schedule)
    expected_penalty_fields = {
        "penalty_status": "projected",
        "projected_penalty": "5.13",
        "assessed_penalty_balance": "1.25",
        "penalty_base": "89.00",
        "remaining_cost_headroom": "4993.62",
        "exact_payoff_total": "96.38",
        "management_review_required_reason": "",
    }
    for key, value in expected_penalty_fields.items():
        assert collector_payload[key] == value
        assert client_payload[key] == value
    assert collector_payload["base_maturity"] == "2026-08-26"
    assert collector_payload["updated_maturity"] == "2026-08-26"
    assert client_payload["contractual_maturity"] == "2026-08-26"
    assert client_payload["operational_maturity"] == "2026-08-26"


def test_collector_repository_does_not_project_penalty_for_regular(monkeypatch) -> None:
    connection = FakeConnection(calculation_mode="fixed_total")

    def forbidden(*args, **kwargs):
        raise AssertionError("Regular schedule must not invoke the 7x7 penalty coordinator")

    monkeypatch.setattr(collector_repository, "open_connection", lambda: connection)
    monkeypatch.setattr(
        collector_repository,
        "project_verified_seven_by_seven_penalty_state",
        forbidden,
        raising=False,
    )

    schedule = PostgresCollectorScheduleRepository().get_schedule(
        collector_user_id=COLLECTOR_ID,
        loan_id=LOAN_ID,
        as_of_date=AS_OF_DATE,
    )

    _assert_neutral_regular_read_model(schedule)


def test_client_repository_uses_shared_penalty_coordinator_for_7x7(monkeypatch) -> None:
    connection = FakeConnection(calculation_mode="seven_by_seven")
    calls: list[tuple[UUID, date]] = []

    def project(cursor, *, loan_id: UUID, as_of_date: date):
        calls.append((loan_id, as_of_date))
        return _penalty_state()

    monkeypatch.setattr(client_repository, "open_connection", lambda: connection)
    monkeypatch.setattr(
        client_repository,
        "project_verified_seven_by_seven_penalty_state",
        project,
        raising=False,
    )

    schedule = PostgresClientLoanRepository().get_schedule_for_user(
        user_id=CLIENT_USER_ID,
        loan_id=LOAN_ID,
        as_of_date=AS_OF_DATE,
    )

    assert calls == [(LOAN_ID, AS_OF_DATE)]
    _assert_projected_read_model(schedule)


def test_client_repository_does_not_project_penalty_for_regular(monkeypatch) -> None:
    connection = FakeConnection(calculation_mode="fixed_total")

    def forbidden(*args, **kwargs):
        raise AssertionError("Regular schedule must not invoke the 7x7 penalty coordinator")

    monkeypatch.setattr(client_repository, "open_connection", lambda: connection)
    monkeypatch.setattr(
        client_repository,
        "project_verified_seven_by_seven_penalty_state",
        forbidden,
        raising=False,
    )

    schedule = PostgresClientLoanRepository().get_schedule_for_user(
        user_id=CLIENT_USER_ID,
        loan_id=LOAN_ID,
        as_of_date=AS_OF_DATE,
    )

    _assert_neutral_regular_read_model(schedule)
