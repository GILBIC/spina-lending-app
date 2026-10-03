from uuid import uuid4

import pytest
from gilbic_backend.treasury_models import COMMAND_ADAPTER
from pydantic import ValidationError


def count(**updates):
    value = {
        "action": "collector_count_record",
        "request_id": str(uuid4()),
        "account_id": str(uuid4()),
        "expected_version": 1,
        "remittance_id": str(uuid4()),
        "source_digest": "a" * 64,
        "counted_amount": "0.00",
        "counted_at": "2026-10-02T08:00:00+08:00",
        "evidence_id": str(uuid4()),
        "review_acknowledged": True,
        "recipient_attestation": "Synthetic count reviewed",
    }
    return dict(value, **updates)


def test_zero_count_is_a_valid_saved_fact_not_a_payment():
    parsed = COMMAND_ADAPTER.validate_python(count())
    assert parsed.counted_amount == "0.00"
    assert parsed.action == "collector_count_record"


def test_ordinary_count_retry_keeps_its_pre_extension_request_hash():
    import hashlib
    import json

    from gilbic_backend.treasury_models import command_hash

    old_body = count()
    old_hash = hashlib.sha256(
        json.dumps(old_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert command_hash(COMMAND_ADAPTER.validate_python(old_body)) == old_hash
    assert (
        command_hash(
            COMMAND_ADAPTER.validate_python(
                dict(
                    old_body,
                    retained_exception_id=None,
                    retained_exception_version=None,
                )
            )
        )
        == old_hash
    )


@pytest.mark.parametrize(
    "selection",
    [
        {"retained_exception_id": str(uuid4())},
        {"retained_exception_version": 1},
    ],
)
def test_retained_selection_requires_both_identity_and_version(selection):
    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(count(**selection))


@pytest.mark.parametrize("amount", ["-1.00", "1.001", 1.0, "10000000000000000.00"])
def test_counts_reject_invalid_money(amount):
    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(count(counted_amount=amount))


@pytest.mark.parametrize("extra", ["required_amount", "actor_user_id", "disposition"])
def test_count_rejects_authoritative_claims(extra):
    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(count(**{extra: "forged"}))


def test_review_flag_does_not_accept_integer_truth():
    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(count(review_acknowledged=1))


def test_own_credit_request_has_no_wallet_authority_fields():
    value = {
        "action": "collector_surplus_return_request",
        "request_id": str(uuid4()),
        "credit_id": str(uuid4()),
        "credit_version": 1,
        "amount": "0.01",
        "destination": {"kind": "physical_cash", "recipient_reference": None},
        "reason": "Please return my recognized credit",
    }
    parsed = COMMAND_ADAPTER.validate_python(value)
    assert parsed.amount == "0.01"
    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(dict(value, account_id=str(uuid4())))
