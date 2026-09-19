"""One request/repayment payload for review, not full T01 or saved confirmation.

Compose the accepted validators; do not duplicate their rules, copy CIF identity
into caller-controlled facts, or turn field completeness into loan approval.
"""
from copy import deepcopy
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from gilbic_backend import loan_application_information as information


def _model():
    model = getattr(information, "LoanApplicationInformation", None)
    assert model is not None, "Combined application-information model is not implemented"
    return model


def _facts():
    return {
        "request": {
            "requested_loan_type_id": "11111111-1111-4111-8111-111111111111",
            "purpose": "  Synthetic   working capital ",
            "requested_amount": "3000.00",
            "requested_payment_arrangement": "Weekly on Thursday, subject to approval",
            "requested_term": "20 requested installments",
            "preferred_first_payment_date": "2026-09-24",
        },
        "repayment": {
            "repayment_source": "business",
            "source_details": "  Synthetic   market stall ",
            "monthly_gross_income": "30000.00",
            "monthly_net_income": "18000.00",
            "has_existing_obligations": True,
            "obligations": [
                {
                    "creditor": "Synthetic lender",
                    "outstanding_balance": "2000.00",
                    "periodic_payment_amount": "100.00",
                    "payment_frequency": "Monthly on the 15th",
                }
            ],
        },
    }


def test_empty_draft_reports_both_sections_without_invented_values():
    draft = _model()()

    assert tuple(type(draft).model_fields) == ("request", "repayment")
    assert isinstance(draft.request, information.LoanRequestInformation)
    assert isinstance(draft.repayment, information.LoanRepaymentInformation)
    assert draft.model_dump() == {
        "request": information.LoanRequestInformation().model_dump(),
        "repayment": information.LoanRepaymentInformation().model_dump(),
    }
    assert draft.missing_fields() == (
        "request.requested_loan_type_id", "request.purpose", "request.requested_amount",
        "request.requested_payment_arrangement", "request.requested_term",
        "repayment.repayment_source", "repayment.source_details",
        "repayment.monthly_gross_income", "repayment.monthly_net_income",
        "repayment.has_existing_obligations",
    )


@pytest.mark.parametrize("omitted", ["request", "repayment"])
def test_one_complete_section_cannot_hide_the_missing_other_section(omitted):
    values = _facts()
    del values[omitted]
    draft = _model()(**values)

    expected = tuple(f"{omitted}.{name}" for name in getattr(draft, omitted).missing_fields())
    assert expected
    assert draft.missing_fields() == expected


def test_missing_paths_include_every_incomplete_debt_row_in_order():
    values = _facts()
    values["request"]["purpose"] = " "
    values["repayment"]["monthly_net_income"] = None
    first = values["repayment"]["obligations"][0]
    second = deepcopy(first)
    first["creditor"] = None
    second["payment_frequency"] = " "
    values["repayment"]["obligations"].append(second)
    draft = _model()(**values)

    assert draft.missing_fields() == (
        "request.purpose", "repayment.monthly_net_income",
        "repayment.obligations[0].creditor", "repayment.obligations[1].payment_frequency",
    )
    assert len(draft.repayment.obligations) == 2


def test_combined_json_round_trip_preserves_normalized_facts_and_exact_money():
    model = _model()
    values = _facts()
    before = deepcopy(values)
    draft = model(**values)
    expected = {
        "request": information.LoanRequestInformation(**values["request"]).model_dump(mode="json"),
        "repayment": information.LoanRepaymentInformation(**values["repayment"]).model_dump(mode="json"),
    }

    assert values == before
    assert draft.model_dump(mode="json") == expected
    assert json.loads(draft.model_dump_json()) == expected
    assert model.model_validate_json(draft.model_dump_json()) == draft
    assert draft.request.requested_amount.as_tuple() == Decimal("3000.00").as_tuple()
    assert draft.repayment.obligations[0].outstanding_balance.as_tuple() == Decimal("2000.00").as_tuple()
    assert draft.missing_fields() == ()  # These two sections only, NOT full T01 readiness.


def test_input_and_export_edits_cannot_silently_rewrite_existing_review_values():
    model = _model()
    values = _facts()
    draft = model(**values)
    exported = draft.model_dump(mode="json")
    values["request"]["requested_amount"] = "5000.00"
    values["repayment"]["obligations"].clear()
    exported["repayment"]["monthly_net_income"] = "0.00"
    changed_draft = model(**values)

    assert draft.request.requested_amount == Decimal("3000.00")
    assert draft.repayment.monthly_net_income == Decimal("18000.00")
    assert len(draft.repayment.obligations) == 1
    assert changed_draft.request.requested_amount == Decimal("5000.00")
    assert changed_draft.missing_fields() == ("repayment.obligations",)
    with pytest.raises(ValidationError):
        draft.request = changed_draft.request
    with pytest.raises(ValidationError):
        draft.repayment.obligations[0].creditor = "Changed"


@pytest.mark.parametrize("section", ["request", "repayment"])
def test_explicit_null_section_is_invalid_not_a_way_to_skip_its_validator(section):
    model = _model()
    values = _facts()
    values[section] = None

    with pytest.raises(ValidationError) as caught:
        model(**values)
    assert caught.value.errors()[0]["loc"] == (section,)


@pytest.mark.parametrize("section, field, invalid", [
    ("request", "requested_amount", "3000.001"),
    ("request", "approved_principal", "3000.00"),
    ("repayment", "monthly_net_income", True),
    ("repayment", "has_existing_obligations", "false"),
    ("repayment", "confirmed_at", "2026-09-17T09:00:00Z"),
])
def test_combined_validation_preserves_nested_rejection_and_error_location(section, field, invalid):
    model = _model()
    values = _facts()
    values[section][field] = invalid

    with pytest.raises(ValidationError) as caught:
        model(**values)
    assert (section, field) in {error["loc"] for error in caught.value.errors()}


@pytest.mark.parametrize("field, value", [
    ("client_id", "11111111-1111-4111-8111-111111111111"),
    ("cif_version_id", "11111111-1111-4111-8111-111111111111"),
    ("confirmed_at", "2026-09-17T09:00:00Z"),
    ("approved_principal", "3000.00"),
    ("ready_for_confirmation", True),
    ("release_status", "released"),
])
def test_request_payload_cannot_supply_identity_confirmation_or_approval_authority(field, value):
    model = _model()
    values = _facts()
    values[field] = value

    with pytest.raises(ValidationError) as caught:
        model(**values)
    assert (field,) in {error["loc"] for error in caught.value.errors()}
