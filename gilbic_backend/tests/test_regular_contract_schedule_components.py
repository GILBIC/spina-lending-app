from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from gilbic_backend import contract_schedule_engine as engine
from gilbic_backend.contract_schedule_registration_api import (
    ContractScheduleTermsRequest,
    _generate_verified_terms,
)


def _regular_terms(*, contractual_total: str = "6000.00") -> ContractScheduleTermsRequest:
    return ContractScheduleTermsRequest(
        loan_id=uuid4(),
        payment_frequency="daily",
        contract_reference="REG-ANNEX-A-TEST",
        contract_signed_date=date(2026, 9, 13),
        effective_from=date(2026, 9, 13),
        contractual_total=Decimal(contractual_total),
        first_due_date=date(2026, 9, 14),
        installment_count=120,
        regular_installment_amount=Decimal("50.00"),
    )


def _regular_context() -> SimpleNamespace:
    return SimpleNamespace(
        calculation_mode="fixed_total",
        principal=Decimal("5000.00"),
        interest_rate=Decimal("20.0000"),
    )


def test_regular_component_preparation_preserves_rows_and_reconciles_exact_totals() -> None:
    source = engine.generate_contract_installments(
        payment_frequency="daily",
        contractual_total=Decimal("6000.00"),
        first_due_date=date(2026, 9, 14),
        installment_count=120,
        regular_installment_amount=Decimal("50.00"),
    )

    prepared = engine.prepare_regular_contract_components(
        installments=source,
        original_principal=Decimal("5000.00"),
        contractual_interest=Decimal("1000.00"),
    )

    assert [row.installment_number for row in prepared] == [
        row.installment_number for row in source
    ]
    assert [row.due_date for row in prepared] == [row.due_date for row in source]
    assert [row.contractual_amount for row in prepared] == [
        row.contractual_amount for row in source
    ]
    assert sum(row.principal_component for row in prepared) == Decimal("5000.00")
    assert sum(row.interest_component for row in prepared) == Decimal("1000.00")
    assert all(
        row.principal_component + row.interest_component == row.contractual_amount
        for row in prepared
    )


def test_regular_component_preparation_reconciles_uneven_cent_rows_without_changing_dates() -> None:
    source = engine.generate_contract_installments(
        payment_frequency="weekly",
        contractual_total=Decimal("1000.00"),
        first_due_date=date(2026, 9, 18),
        installment_count=3,
    )

    prepared = engine.prepare_regular_contract_components(
        installments=source,
        original_principal=Decimal("800.00"),
        contractual_interest=Decimal("200.00"),
    )

    assert [row.contractual_amount for row in prepared] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert [row.due_date for row in prepared] == [
        date(2026, 9, 18),
        date(2026, 9, 25),
        date(2026, 10, 2),
    ]
    assert sum(row.principal_component for row in prepared) == Decimal("800.00")
    assert sum(row.interest_component for row in prepared) == Decimal("200.00")
    assert prepared[-1].principal_component + prepared[-1].interest_component == Decimal(
        "333.34"
    )


def test_regular_component_preparation_does_not_mutate_uncomponentized_source_rows() -> None:
    source = engine.generate_contract_installments(
        payment_frequency="semi_monthly",
        contractual_total=Decimal("1200.00"),
        first_due_date=date(2026, 9, 15),
        installment_count=4,
        regular_installment_amount=Decimal("300.00"),
        semi_monthly_days=(15, 30),
    )

    prepared = engine.prepare_regular_contract_components(
        installments=source,
        original_principal=Decimal("1000.00"),
        contractual_interest=Decimal("200.00"),
    )

    assert all(getattr(row, "principal_component", None) is None for row in source)
    assert all(getattr(row, "interest_component", None) is None for row in source)
    assert all(row.principal_component is not None for row in prepared)
    assert all(row.interest_component is not None for row in prepared)


def test_regular_component_preparation_rejects_totals_that_do_not_match_schedule() -> None:
    source = engine.generate_contract_installments(
        payment_frequency="monthly",
        contractual_total=Decimal("1200.00"),
        first_due_date=date(2026, 9, 30),
        installment_count=2,
        regular_installment_amount=Decimal("600.00"),
    )

    with pytest.raises(engine.ContractScheduleError, match="principal plus interest"):
        engine.prepare_regular_contract_components(
            installments=source,
            original_principal=Decimal("1000.00"),
            contractual_interest=Decimal("150.00"),
        )


def test_regular_registration_terms_include_components_from_authoritative_principal_and_interest_rate() -> None:
    rows = _generate_verified_terms(_regular_terms(), _regular_context())

    assert len(rows) == 120
    assert sum(row.contractual_amount for row in rows) == Decimal("6000.00")
    assert sum(row.principal_component for row in rows) == Decimal("5000.00")
    assert sum(row.interest_component for row in rows) == Decimal("1000.00")
    assert all(
        row.principal_component + row.interest_component == row.contractual_amount
        for row in rows
    )


def test_regular_registration_rejects_contractual_total_that_is_not_principal_plus_approved_interest() -> None:
    with pytest.raises(HTTPException) as error:
        _generate_verified_terms(
            _regular_terms(contractual_total="6100.00"),
            _regular_context(),
        )

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "regular_contractual_total_mismatch"


def test_regular_component_preparation_rejects_non_cent_or_negative_authoritative_values() -> None:
    source = engine.generate_contract_installments(
        payment_frequency="balloon",
        contractual_total=Decimal("1200.00"),
        first_due_date=date(2026, 10, 1),
        installment_count=1,
    )

    with pytest.raises(engine.ContractScheduleError):
        engine.prepare_regular_contract_components(
            installments=source,
            original_principal=Decimal("1000.001"),
            contractual_interest=Decimal("199.999"),
        )

    with pytest.raises(engine.ContractScheduleError):
        engine.prepare_regular_contract_components(
            installments=source,
            original_principal=Decimal("1000.00"),
            contractual_interest=Decimal("-1.00"),
        )
