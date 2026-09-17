"""T01 section II request facts, NOT a complete application or an approval.

Keep the reusable Client/CIF and authenticated evidence outside this small
value model. Product existence, allowed arrangements and pricing still require
stored authoritative sources. No request field creates approved loan terms.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from importlib import import_module
from uuid import UUID

import pytest
from pydantic import ValidationError


MODULE = "gilbic_backend.loan_application_information"
REQUEST_FIELDS = (
    "requested_loan_type_id",
    "purpose",
    "requested_amount",
    "requested_payment_arrangement",
    "requested_term",
)
ALL_FIELDS = (*REQUEST_FIELDS, "preferred_first_payment_date")
LOAN_TYPE_ID = UUID("11111111-1111-4111-8111-111111111111")


def _model():
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        pytest.fail("Loan-request information model is not implemented", pytrace=False)
    model = getattr(module, "LoanRequestInformation", None)
    assert model is not None, "LoanRequestInformation is not implemented"
    return model


def _request(**changes):
    values = {
        "requested_loan_type_id": str(LOAN_TYPE_ID),
        "purpose": "Synthetic working capital request",
        "requested_amount": "10000.00",
        "requested_payment_arrangement": "Daily collection, subject to approval",
        "requested_term": "120 requested collection installments",
    }
    values.update(changes)
    return values


def test_empty_draft_reports_missing_request_fields_without_guessing_defaults():
    draft = _model()()

    assert tuple(type(draft).model_fields) == ALL_FIELDS
    assert draft.model_dump() == dict.fromkeys(ALL_FIELDS)
    assert draft.missing_fields() == REQUEST_FIELDS


@pytest.mark.parametrize("missing", REQUEST_FIELDS)
def test_partial_draft_reports_the_exact_missing_request_field(missing):
    values = _request()
    values.pop(missing)
    draft = _model()(**values)

    assert getattr(draft, missing) is None
    assert draft.missing_fields() == (missing,)


def test_blank_text_is_incomplete_not_an_invented_purpose_arrangement_or_term():
    draft = _model()(**_request(
        purpose="  ", requested_payment_arrangement="\t", requested_term="\n"
    ))

    assert draft.missing_fields() == (
        "purpose", "requested_payment_arrangement", "requested_term"
    )
    assert draft.purpose is None
    assert draft.requested_payment_arrangement is None
    assert draft.requested_term is None


@pytest.mark.parametrize("arrangement, term", [
    ("Daily; Sundays and declared holidays excluded", "120 collection installments"),
    ("Weekly on Thursday", "20 requested weeks"),
    ("Semi-monthly on the 15th and last day", "8 requested installments"),
    ("Monthly on the 10th", "4 requested months"),
    ("Custom dates, to be checked against the selected product", "As requested below"),
])
def test_requested_arrangement_and_term_are_preserved_not_interpreted_as_approval(
    arrangement, term
):
    draft = _model()(**_request(
        requested_payment_arrangement=arrangement, requested_term=term
    ))

    assert draft.missing_fields() == ()  # Only section II is complete.
    assert draft.requested_loan_type_id == LOAN_TYPE_ID
    assert draft.requested_amount == Decimal("10000.00")
    assert draft.requested_payment_arrangement == arrangement
    assert draft.requested_term == term
    assert draft.preferred_first_payment_date is None
    assert set(draft.model_dump()) == set(ALL_FIELDS)


def test_normalization_preserves_exact_money_and_never_mutates_the_input():
    values = _request(purpose="  Synthetic   stock purchase ",
                      requested_amount="3000.00",
                      preferred_first_payment_date="2026-09-18")
    before = deepcopy(values)
    draft = _model()(**values)

    assert values == before
    assert draft.purpose == "Synthetic stock purchase"
    assert draft.requested_amount.as_tuple() == Decimal("3000.00").as_tuple()
    assert draft.preferred_first_payment_date == date(2026, 9, 18)
    assert draft.model_dump(mode="json")["requested_amount"] == "3000.00"
    assert draft.missing_fields() == ()
    with pytest.raises(ValidationError):
        draft.requested_amount = Decimal("4000.00")
    assert draft.requested_amount == Decimal("3000.00")


@pytest.mark.parametrize("amount", [
    "0", "-1.00", "NaN", "Infinity", "10000.001", True, 10000.1, "not money"
])
def test_supplied_amount_must_be_positive_finite_exact_cent_money(amount):
    model = _model()

    with pytest.raises(ValidationError):
        model(**_request(requested_amount=amount))


@pytest.mark.parametrize("field, value", [
    ("approved_principal", "12000.00"),
    ("interest_rate", "0.20"),
    ("confirmed_at", "2026-09-18T09:00:00Z"),
    ("approved_by_user_id", str(LOAN_TYPE_ID)),
    ("cif_version_id", str(LOAN_TYPE_ID)),
    ("release_status", "released"),
])
def test_request_cannot_supply_authoritative_profile_approval_or_release_fields(
    field, value
):
    model = _model()

    with pytest.raises(ValidationError):
        model(**_request(**{field: value}))


@pytest.mark.parametrize("field, value", [
    ("requested_loan_type_id", "Regular"),
    ("purpose", {"unsafe": "not text"}),
    ("requested_term", 120),  # Never guess days, months or paying installments.
    ("preferred_first_payment_date", "2026-02-30"),
])
def test_invalid_supplied_values_are_rejected_instead_of_coerced_or_defaulted(
    field, value
):
    model = _model()

    with pytest.raises(ValidationError):
        model(**_request(**{field: value}))
