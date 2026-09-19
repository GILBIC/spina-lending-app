from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from gilbic_backend import loan_application_information as module


def _parse(value):
    parser = getattr(module, "parse_loan_application_information", None)
    assert parser is not None, "Extended application information is not implemented"
    return parser(value)


def _details():
    return {"schema_version": 1, "employment": {
        "employer_or_business_name": "Synthetic store", "position_or_business_nature": "Retail",
        "length_of_employment_or_operation": "Two years", "employer_or_business_address": "Synthetic store address",
        "contact_number": "00000000000",
    }, "references": [{"full_name": "Synthetic contact", "relationship": "Sibling", "phone_number": "00000000001", "address": "Synthetic contact address"}]}


def _facts():
    return {"request": {"requested_amount": "9007199254740993.01"}, "repayment": {}, "details": _details()}


def test_legacy_model_fields_json_and_parser_type_stay_unchanged():
    original = module.LoanApplicationInformation(request={"requested_amount": "9007199254740993.01"})
    serialized = original.model_dump(mode="json")
    parsed = _parse(serialized)
    assert type(parsed) is module.LoanApplicationInformation
    assert tuple(module.LoanApplicationInformation.model_fields) == ("request", "repayment")
    assert parsed.model_dump(mode="json") == serialized
    assert set(json.loads(parsed.model_dump_json())) == {"request", "repayment"}


def test_extended_facts_round_trip_exact_money_and_normalized_declarations_without_changing_input():
    values = _facts()
    values["details"]["employment"]["employer_or_business_name"] = " Synthetic   store "
    values["details"]["references"][0]["relationship"] = " Sibling "
    before = deepcopy(values)
    model = _parse(values)
    dumped = model.model_dump(mode="json")
    assert dumped["details"] == _details()
    assert dumped["request"]["requested_amount"] == "9007199254740993.01"
    assert _parse(json.loads(model.model_dump_json())) == model
    assert values == before


@pytest.mark.parametrize("rows", [0, 1, 3, 8])
def test_optional_references_have_no_invented_quota(rows):
    values = _facts()
    values["details"]["references"] = [{} for _ in range(rows)]
    model = _parse(values)
    assert len(model.details.references) == rows
    assert all(row.full_name is None for row in model.details.references)
    assert model.missing_fields() == module.LoanApplicationInformation(request=values["request"]).missing_fields()


def test_blank_details_are_nullable_and_do_not_claim_verification_or_required_business_policy():
    model = _parse({"details": {"employment": {"contact_number": "  "}}})
    assert model.details.schema_version == 1
    assert model.details.employment.contact_number is None
    assert model.details.references == ()
    assert "confirmed" not in model.model_dump_json()
    assert model.missing_fields() == module.LoanApplicationInformation().missing_fields()


@pytest.mark.parametrize("version", [0, 2, "1", True, None])
def test_details_schema_version_is_exact_integer_one(version):
    with pytest.raises(ValidationError):
        _parse({"details": {"schema_version": version}})


@pytest.mark.parametrize("location,key,value", [
    ("employment", "contact_number", 123), ("employment", "employer_or_business_name", True),
    ("reference", "phone_number", []), ("reference", "address", {}),
    ("details", "approved_principal", "1000.00"), ("details", "client_id", "copied-identity"),
    ("details", "verified", True), ("details", "privacy_consent", True),
])
def test_details_reject_wrong_types_and_fields_owned_by_other_authorities(location, key, value):
    values = _facts()
    target = values["details"]["employment"] if location == "employment" else values["details"]["references"][0] if location == "reference" else values["details"]
    target[key] = value
    with pytest.raises(ValidationError):
        _parse(values)


def test_extended_snapshot_and_nested_declarations_are_frozen():
    model = _parse(_facts())
    with pytest.raises(ValidationError):
        model.details.employment.contact_number = "changed"
    with pytest.raises(ValidationError):
        model.details.references[0].full_name = "changed"
    edited_export = model.model_dump(mode="json")
    edited_export["details"]["employment"]["employer_or_business_name"] = "changed"
    assert model.details.employment.employer_or_business_name == "Synthetic store"


def test_explicit_null_extension_does_not_rewrite_legacy_json_shape():
    assert _parse({"details": None}).model_dump(mode="json") == module.LoanApplicationInformation().model_dump(mode="json")
