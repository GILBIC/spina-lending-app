from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import HTTPException

from gilbic_backend.contract_schedule_registration_api import (
    ContractScheduleTermsRequest,
    _generate_verified_terms,
    _installment_payload,
)
from gilbic_backend.contract_schedule_registration_repository import (
    ContractScheduleLoanContext,
)


def _context(*, calculation_mode: str = "seven_by_seven") -> ContractScheduleLoanContext:
    return ContractScheduleLoanContext(
        loan_id=UUID("00000000-0000-0000-0000-000000000101"),
        loan_number="X7-SIGNED-001",
        client_code="CLIENT-001",
        client_name="Signed 7x7 Client",
        loan_type_name="7x7",
        calculation_mode=calculation_mode,
        daily_interest_per_1000=Decimal("7.00"),
        principal=Decimal("3000.00"),
        daily_amount=Decimal("21.00"),
        date_released=date(2026, 8, 26),
        due_date=date(2026, 12, 24),
        loan_status="active",
        active_schedule_id=None,
        active_schedule_version=None,
        active_payment_frequency=None,
        active_contract_reference=None,
    )


def _seven_by_seven_request(**overrides) -> ContractScheduleTermsRequest:
    values = {
        "loan_id": UUID("00000000-0000-0000-0000-000000000101"),
        "payment_frequency": "daily",
        "contract_reference": "SIGNED-X7-001",
        "contract_signed_date": date(2026, 8, 26),
        "effective_from": date(2026, 8, 26),
        "first_due_date": date(2026, 8, 27),
        "agreed_daily_payment": Decimal("50.00"),
    }
    values.update(overrides)
    return ContractScheduleTermsRequest(**values)


def test_verified_7x7_terms_use_authoritative_principal_rate_and_agreed_payment() -> None:
    rows = _generate_verified_terms(_seven_by_seven_request(), _context())

    assert len(rows) == 104
    assert rows[0].contractual_amount == Decimal("50.00")
    assert rows[0].principal_component == Decimal("29.00")
    assert rows[0].interest_component == Decimal("21.00")
    assert rows[-1].contractual_amount == Decimal("34.00")
    assert rows[-1].principal_component == Decimal("13.00")
    assert rows[-1].interest_component == Decimal("21.00")
    assert sum(row.principal_component for row in rows) == Decimal("3000.00")

    first_payload = _installment_payload(rows[0])
    assert first_payload["contractual_amount"] == "50.00"
    assert first_payload["principal_component"] == "29.00"
    assert first_payload["interest_component"] == "21.00"


def test_verified_7x7_terms_reject_generic_row_inputs_and_total_mismatch() -> None:
    with pytest.raises(HTTPException) as generic_rows_error:
        _generate_verified_terms(
            _seven_by_seven_request(installment_count=120),
            _context(),
        )
    assert generic_rows_error.value.status_code == 422
    assert generic_rows_error.value.detail["code"] == "conflicting_7x7_schedule_terms"

    with pytest.raises(HTTPException) as total_error:
        _generate_verified_terms(
            _seven_by_seven_request(contractual_total=Decimal("9999.00")),
            _context(),
        )
    assert total_error.value.status_code == 422
    assert total_error.value.detail["code"] == "7x7_contractual_total_mismatch"


def test_non_7x7_schedule_still_requires_generic_contractual_total() -> None:
    with pytest.raises(HTTPException) as error:
        _generate_verified_terms(
            ContractScheduleTermsRequest(
                loan_id=UUID("00000000-0000-0000-0000-000000000101"),
                payment_frequency="daily",
                contract_reference="REG-001",
                contract_signed_date=date(2026, 8, 26),
                effective_from=date(2026, 8, 26),
                first_due_date=date(2026, 8, 27),
                installment_count=3,
                regular_installment_amount=Decimal("100.00"),
            ),
            _context(calculation_mode="custom"),
        )
    assert error.value.status_code == 422
    assert error.value.detail["code"] == "missing_contractual_total"
