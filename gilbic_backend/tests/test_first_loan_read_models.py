from dataclasses import replace
from datetime import date
from types import SimpleNamespace

from test_client_loan_api import FakeLoans, CLIENT_USER_ID
from gilbic_backend.client_loan_api import _loan_payload
from gilbic_backend.contract_schedule_registration_api import _loan_context_payload


def test_client_first_payment_is_an_explicit_persisted_date_not_release_plus_one():
    record = FakeLoans().list_for_user(user_id=CLIENT_USER_ID).loans[0]
    assert _loan_payload(record)["first_payment_date"] is None
    record = replace(record, first_payment_date=date(2026, 9, 28))
    assert _loan_payload(record)["first_payment_date"] == "2026-09-28"
    record = replace(
        record,
        date_released=None,
        due_date=None,
        first_payment_date=None,
        status="approved",
    )
    assert _loan_payload(record)["date_released"] is None
    assert _loan_payload(record)["first_payment_date"] is None


def test_unreleased_contract_context_has_real_null_dates():
    context = SimpleNamespace(
        loan_id=CLIENT_USER_ID,
        loan_number="SYNTHETIC",
        client_code="SYNTHETIC",
        client_name="Synthetic",
        loan_type_name="Regular",
        calculation_mode="fixed_daily",
        daily_interest_per_1000=0,
        principal=1000,
        daily_amount=100,
        date_released=None,
        due_date=None,
        loan_status="approved",
        active_schedule_id=None,
        active_schedule_version=None,
        active_payment_frequency=None,
        active_contract_reference=None,
        interest_rate=10,
    )
    payload = _loan_context_payload(context)
    assert payload["date_released"] is None
    assert payload["due_date"] is None
