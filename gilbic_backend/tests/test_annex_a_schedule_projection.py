"""Synthetic Annex A source-binding contract; no live-loan pricing is approved.

Fixtures come from the existing signed 7x7 generator. The document projection
must copy those rows, not generate a second contractual/operational schedule.
PDF layout, production provenance, signing and storage are later acceptance.
"""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from importlib.util import find_spec

import pytest

from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


MODULE = "gilbic_backend.annex_a_schedule_projection"


def _projection_module():
    # A missing implementation must be a clear test failure, not collection loss.
    assert find_spec(MODULE) is not None, (
        "Annex A source projection is intentionally absent at the TDD RED step."
    )
    return import_module(MODULE)


def _signed_rows(principal="3000.00", daily="50.00"):
    return generate_signed_seven_by_seven_schedule(
        original_principal=principal,
        agreed_daily_payment=daily,
        daily_interest_per_1000="7.00",
        first_due_date=date(2026, 9, 13),
    )


def _project(rows, *, principal="3000.00", **overrides):
    values = {
        "original_principal": Decimal(principal),
        "installments": rows,
        "expected_installment_count": len(rows),
        "expected_first_due_date": rows[0].due_date,
        "expected_maturity_date": rows[-1].due_date,
        "expected_total_payable": sum(
            (row.contractual_amount for row in rows), Decimal("0.00")
        ),
    }
    values.update(overrides)
    return _projection_module().project_seven_by_seven_annex_a(**values)


@pytest.mark.parametrize(
    ("principal", "daily", "count"),
    [
        ("1000.00", "1007.00", 1),
        ("1000.00", "150.00", 7),
        ("1000.00", "140.00", 8),
        ("3000.00", "71.00", 60),
        ("3000.00", "50.00", 104),
    ],
)
def test_annex_a_preserves_every_authoritative_row(principal, daily, count):
    rows = _signed_rows(principal, daily)
    assert len(rows) == count  # Check the existing generator before new binding.
    before = tuple(rows)
    result = _project(rows, principal=principal)

    assert len(result.rows) == count
    assert [row.installment_number for row in result.rows] == list(range(1, count + 1))
    for source, displayed in zip(rows, result.rows, strict=True):
        assert displayed.due_date == source.due_date
        assert displayed.contractual_amount == source.contractual_amount
        assert displayed.principal_component == source.principal_component
        assert displayed.interest_component == source.interest_component
    assert rows == before
    assert result.maturity_date == rows[-1].due_date
    assert result.total_principal == Decimal(principal)
    assert result.total_interest == sum(
        (row.interest_component for row in rows), Decimal("0.00")
    )
    assert result.total_due == sum(
        (row.contractual_amount for row in rows), Decimal("0.00")
    )


def test_annex_a_scheduled_remaining_principal_excludes_interest():
    result = _project(_signed_rows())

    assert result.balance_label == "Scheduled Remaining Principal"
    assert result.rows[0].scheduled_remaining_principal == Decimal("2971.00")
    assert result.rows[59].scheduled_remaining_principal == Decimal("1260.00")
    assert result.rows[102].scheduled_remaining_principal == Decimal("13.00")
    assert result.rows[103].scheduled_remaining_principal == Decimal("0.00")
    assert result.rows[103].contractual_amount == Decimal("34.00")
    assert result.total_interest == Decimal("2184.00")
    assert result.total_due == Decimal("5184.00")
    assert result.maturity_date == date(2026, 12, 25)
    assert all(
        isinstance(row.scheduled_remaining_principal, Decimal)
        for row in result.rows
    )


@pytest.mark.parametrize(
    "field",
    [
        "original_principal",
        "installments",
        "expected_installment_count",
        "expected_first_due_date",
        "expected_maturity_date",
        "expected_total_payable",
    ],
)
def test_annex_a_rejects_missing_required_source_values(field):
    module = _projection_module()
    with pytest.raises(module.AnnexAProjectionError):
        _project(_signed_rows(), **{field: None})


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered", "empty"])
def test_annex_a_rejects_partial_duplicate_or_reordered_source_rows(mutation):
    rows = _signed_rows()
    if mutation == "missing":
        changed = rows[:7] + rows[8:]
    elif mutation == "duplicate":
        changed = rows[:7] + (rows[6],) + rows[7:]
    elif mutation == "reordered":
        changed = (rows[1], rows[0]) + rows[2:]
    else:
        changed = ()
    module = _projection_module()
    with pytest.raises(module.AnnexAProjectionError):
        _project(rows, installments=changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("original_principal", Decimal("3000.01")),
        ("expected_installment_count", 60),
        ("expected_first_due_date", date(2026, 9, 14)),
        ("expected_maturity_date", date(2026, 11, 11)),
        ("expected_total_payable", Decimal("5184.01")),
    ],
)
def test_annex_a_rejects_terms_that_disagree_with_the_signed_rows(field, value):
    module = _projection_module()
    with pytest.raises(module.AnnexAProjectionError):
        _project(_signed_rows(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("principal_component", Decimal("-0.01")),
        ("principal_component", Decimal("29.001")),
        ("principal_component", Decimal("NaN")),
        ("interest_component", Decimal("Infinity")),
        ("interest_component", Decimal("-1.00")),
        ("contractual_amount", Decimal("50.01")),
    ],
)
def test_annex_a_rejects_invalid_money_without_silent_rounding(field, value):
    rows = _signed_rows()
    changed = (replace(rows[0], **{field: value}),) + rows[1:]
    module = _projection_module()
    with pytest.raises(module.AnnexAProjectionError):
        _project(rows, installments=changed)


def test_annex_a_rejects_an_interior_date_gap_without_repairing_it():
    rows = _signed_rows()
    changed = (
        rows[:7]
        + (replace(rows[7], due_date=rows[7].due_date + timedelta(days=1)),)
        + rows[8:]
    )
    module = _projection_module()
    with pytest.raises(module.AnnexAProjectionError):
        _project(rows, installments=changed)


def test_annex_a_repeated_projection_keeps_the_signed_source_unchanged():
    rows = _signed_rows()
    before = tuple(rows)
    first = _project(rows)
    second = _project(rows)

    assert first == second
    assert rows == before
    assert tuple(row.principal_component for row in rows) == (
        (Decimal("29.00"),) * 103 + (Decimal("13.00"),)
    )
