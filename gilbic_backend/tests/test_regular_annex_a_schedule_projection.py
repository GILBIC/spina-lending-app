from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend import annex_a_schedule_projection as projection
from gilbic_backend.contract_schedule_engine import (
    generate_contract_installments,
    prepare_regular_contract_components,
)


def _regular_rows(
    *,
    payment_frequency: str = "daily",
    contractual_total: str = "6000.00",
    principal: str = "5000.00",
    interest: str = "1000.00",
    first_due_date: date = date(2026, 9, 14),
    installment_count: int = 120,
    regular_installment_amount: str | None = "50.00",
):
    generic = generate_contract_installments(
        payment_frequency=payment_frequency,
        contractual_total=Decimal(contractual_total),
        first_due_date=first_due_date,
        installment_count=installment_count,
        regular_installment_amount=(
            Decimal(regular_installment_amount)
            if regular_installment_amount is not None
            else None
        ),
    )
    return prepare_regular_contract_components(
        installments=generic,
        original_principal=Decimal(principal),
        contractual_interest=Decimal(interest),
    )


def _project_regular(rows, *, principal: str, total: str):
    assert hasattr(projection, "project_regular_annex_a"), (
        "Regular Annex A projection is intentionally missing at this TDD RED step."
    )
    return projection.project_regular_annex_a(
        original_principal=Decimal(principal),
        installments=rows,
        expected_installment_count=len(rows),
        expected_first_due_date=rows[0].due_date,
        expected_maturity_date=rows[-1].due_date,
        expected_total_payable=Decimal(total),
    )


def test_regular_annex_a_preserves_approved_120_row_schedule_and_components() -> None:
    rows = _regular_rows()
    before = tuple(rows)

    result = _project_regular(rows, principal="5000.00", total="6000.00")

    assert len(result.rows) == 120
    assert result.maturity_date == date(2027, 1, 11)
    assert result.total_principal == Decimal("5000.00")
    assert result.total_interest == Decimal("1000.00")
    assert result.total_due == Decimal("6000.00")
    assert result.rows[-1].scheduled_remaining_principal == Decimal("0.00")
    assert rows == before
    for source, displayed in zip(rows, result.rows, strict=True):
        assert displayed.installment_number == source.installment_number
        assert displayed.due_date == source.due_date
        assert displayed.contractual_amount == source.contractual_amount
        assert displayed.principal_component == source.principal_component
        assert displayed.interest_component == source.interest_component


def test_regular_annex_a_accepts_authoritative_non_daily_due_dates() -> None:
    generic = generate_contract_installments(
        payment_frequency="semi_monthly",
        contractual_total=Decimal("1200.00"),
        first_due_date=date(2026, 9, 15),
        installment_count=4,
        regular_installment_amount=Decimal("300.00"),
        semi_monthly_days=(15, 30),
    )
    rows = prepare_regular_contract_components(
        installments=generic,
        original_principal=Decimal("1000.00"),
        contractual_interest=Decimal("200.00"),
    )

    result = _project_regular(rows, principal="1000.00", total="1200.00")

    assert [row.due_date for row in result.rows] == [
        date(2026, 9, 15),
        date(2026, 9, 30),
        date(2026, 10, 15),
        date(2026, 10, 30),
    ]
    assert result.total_principal == Decimal("1000.00")
    assert result.total_interest == Decimal("200.00")
    assert result.rows[-1].scheduled_remaining_principal == Decimal("0.00")


def test_regular_annex_a_rejects_duplicate_or_reordered_due_dates() -> None:
    rows = _regular_rows(
        payment_frequency="weekly",
        contractual_total="1200.00",
        principal="1000.00",
        interest="200.00",
        first_due_date=date(2026, 9, 18),
        installment_count=4,
        regular_installment_amount="300.00",
    )
    changed = (rows[0], replace(rows[1], due_date=rows[0].due_date)) + rows[2:]

    assert hasattr(projection, "project_regular_annex_a"), (
        "Regular Annex A projection is intentionally missing at this TDD RED step."
    )
    with pytest.raises(projection.AnnexAProjectionError):
        projection.project_regular_annex_a(
            original_principal=Decimal("1000.00"),
            installments=changed,
            expected_installment_count=4,
            expected_first_due_date=rows[0].due_date,
            expected_maturity_date=rows[-1].due_date,
            expected_total_payable=Decimal("1200.00"),
        )


def test_regular_annex_a_rejects_uncomponentized_rows() -> None:
    generic = generate_contract_installments(
        payment_frequency="monthly",
        contractual_total=Decimal("1200.00"),
        first_due_date=date(2026, 9, 30),
        installment_count=2,
        regular_installment_amount=Decimal("600.00"),
    )

    assert hasattr(projection, "project_regular_annex_a"), (
        "Regular Annex A projection is intentionally missing at this TDD RED step."
    )
    with pytest.raises(projection.AnnexAProjectionError):
        projection.project_regular_annex_a(
            original_principal=Decimal("1000.00"),
            installments=generic,
            expected_installment_count=2,
            expected_first_due_date=generic[0].due_date,
            expected_maturity_date=generic[-1].due_date,
            expected_total_payable=Decimal("1200.00"),
        )
