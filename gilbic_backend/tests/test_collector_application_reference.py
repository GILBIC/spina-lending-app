"""Incomplete application references must never silently become cash-only counts."""

from uuid import uuid4

import pytest
from gilbic_backend.treasury_models import CollectorCountAccept, SettlementPreview
from pydantic import ValidationError


def _payload(model):
    data = {"account_id": uuid4(), "expected_version": 1}
    if model is CollectorCountAccept:
        data.update(
            action="collector_count_accept",
            request_id=uuid4(),
            count_id=uuid4(),
            count_version=1,
            source_digest="a" * 64,
            physical_receipt_acknowledged=True,
        )
    return data


@pytest.mark.parametrize("model", [SettlementPreview, CollectorCountAccept])
@pytest.mark.parametrize(
    "field", ["credit_application_id", "credit_application_version"]
)
def test_partial_credit_application_reference_is_rejected(model, field):
    payload = _payload(model)
    payload[field] = uuid4() if field.endswith("_id") else 1
    with pytest.raises(ValidationError, match="together"):
        model.model_validate(payload)


@pytest.mark.parametrize("model", [SettlementPreview, CollectorCountAccept])
@pytest.mark.parametrize("with_application", [False, True])
def test_cash_only_and_complete_application_references_retain_their_shape(
    model, with_application
):
    payload = _payload(model)
    if with_application:
        payload.update(credit_application_id=uuid4(), credit_application_version=1)
    command = model.model_validate(payload)
    assert command.credit_application_id == payload.get("credit_application_id")
    assert command.credit_application_version == payload.get(
        "credit_application_version"
    )
