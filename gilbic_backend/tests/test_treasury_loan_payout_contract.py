"""Loan payout contracts cannot confuse destination choice with money received."""

from importlib import import_module
from uuid import uuid4

import pytest
from pydantic import ValidationError


def model(name):
    value = getattr(import_module("gilbic_backend.treasury_models"), name, None)
    assert value is not None, "Typed protected loan payout commands are required"
    return value


def preview(**changes):
    values = {
        "account_id": uuid4(),
        "expected_version": 1,
        "source_kind": "first_loan",
        "source_id": uuid4(),
        "recipient_reference": "SYNTHETIC-RECIPIENT-001",
        "authorization_id": uuid4(),
        "packet_hash": "a" * 64,
        "contract_evidence_reference": "office-evidence:" + str(uuid4()),
    }
    values.update(changes)
    return values


def test_default_collector_destination_remains_a_reviewed_choice_not_receipt():
    command = model("LoanPayoutPreview")(**preview())
    assert command.destination == "collector"
    assert "destination_confirmed" not in command.model_dump()
    with pytest.raises(ValidationError):
        model("LoanPayoutPreview")(**preview(destination_confirmed=True))


def test_direct_borrower_destination_is_explicit_and_cannot_select_arbitrary_payee():
    assert (
        model("LoanPayoutPreview")(**preview(destination="borrower")).destination
        == "borrower"
    )
    for field in ("payee_id", "collector_user_id", "client_id", "amount"):
        with pytest.raises(ValidationError):
            model("LoanPayoutPreview")(**preview(**{field: str(uuid4())}))


@pytest.mark.parametrize(
    "field", ["authorization_id", "packet_hash", "contract_evidence_reference"]
)
def test_first_loan_requires_exact_authorization_and_signed_packet_identity(field):
    values = preview()
    values.pop(field)
    with pytest.raises(ValidationError):
        model("LoanPayoutPreview")(**values)


def test_renewal_does_not_accept_unrelated_first_loan_authority():
    values = preview(source_kind="renewal")
    with pytest.raises(ValidationError):
        model("LoanPayoutPreview")(**values)
    for field in ("authorization_id", "packet_hash", "contract_evidence_reference"):
        values.pop(field)
    assert model("LoanPayoutPreview")(**values).source_kind == "renewal"


@pytest.mark.parametrize(
    "changes", [{"destination": "third_party"}, {"recipient_reference": " "}]
)
def test_unknown_destination_and_blank_recipient_do_not_authorize_payout(changes):
    with pytest.raises(ValidationError):
        model("LoanPayoutPreview")(**preview(**changes))


def test_preparation_is_bound_to_the_exact_reviewed_source_digest():
    values = preview(request_id=uuid4(), action="loan_payout_prepare")
    with pytest.raises(ValidationError):
        model("LoanPayoutPrepare")(**values)
    command = model("LoanPayoutPrepare")(**values, source_digest="b" * 64)
    assert command.source_digest == "b" * 64
    module = import_module("gilbic_backend.treasury_models")
    assert (
        module.COMMAND_ADAPTER.validate_python(command.model_dump(mode="json"))
        == command
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"received": "true"},
        {"acknowledged_at": "2026-10-03T10:00:00"},
        {"reviewed_amount": "0.00"},
    ],
)
def test_recipient_confirmation_requires_strict_actual_receipt_fields(changes):
    values = {
        "action": "loan_payout_recipient_confirm",
        "request_id": uuid4(),
        "account_id": uuid4(),
        "expected_version": 2,
        "payout_id": uuid4(),
        "payout_version": 2,
        "evidence_id": uuid4(),
        "reviewed_amount": "9000.00",
        "received": True,
        "acknowledged_at": "2026-10-03T10:00:00+08:00",
        "recipient_attestation": "Exact named recipient confirmed actual receipt.",
    }
    values.update(changes)
    with pytest.raises(ValidationError):
        model("LoanPayoutRecipientConfirm")(**values)


def test_portal_strict_command_schemas_match_the_backend_contract():
    import json
    from pathlib import Path

    from gilbic_backend.treasury_models import COMMAND_ADAPTER

    source = (
        Path(__file__).resolve().parents[2]
        / "spina_portal/assets/loan-payout-schemas.js"
    ).read_text(encoding="utf-8")
    schema = json.loads(source.split("=", 1)[1].strip().removesuffix(";"))
    expected = {
        key: value
        for key, value in COMMAND_ADAPTER.json_schema()["$defs"].items()
        if key.startswith("LoanPayout")
    }
    assert schema == expected
