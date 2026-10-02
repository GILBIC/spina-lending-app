from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_commands_reject_forged_authority_and_inexact_money():
    from gilbic_backend.treasury_models import ReceiptVerify

    payload = dict(action='receipt_verify', request_id=str(uuid4()), account_id=str(uuid4()),
                   expected_version=1, client_id=str(uuid4()), amount='100.00',
                   provider='gcash', reference='00001', effective_at='2026-10-02T00:00:00Z',
                   evidence_id=str(uuid4()), recipient_attestation='Checked recipient transaction history')
    assert ReceiptVerify.model_validate(payload).amount == '100.00'
    for changed in ({'amount': 100.0}, {'amount':'100.001'}, {'amount':'0.00'},
                    {'verified_by_user_id':str(uuid4())}, {'effective_at':'2026-10-02T00:00:00'}):
        with pytest.raises(ValidationError):
            ReceiptVerify.model_validate(payload | changed)


def test_opening_explicit_zero_and_canonical_recovery_identity():
    from gilbic_backend.treasury_models import OpeningPrepare, command_hash

    body = dict(action='opening_prepare', request_id=str(uuid4()), account_id=str(uuid4()),
                expected_version=1, cutoff='2026-10-02T00:00:00Z', amount='0.00',
                evidence_id=str(uuid4()), reason='Synthetic counted opening')
    command = OpeningPrepare.model_validate(body)
    assert command.amount == '0.00'
    assert command_hash(command) == command_hash(OpeningPrepare.model_validate(body))
    assert command_hash(command) != command_hash(OpeningPrepare.model_validate(body | {'amount':'1.00'}))


def test_unknown_action_and_float_allocation_fail_closed():
    from gilbic_backend.treasury_models import COMMAND_ADAPTER, Allocation

    with pytest.raises(ValidationError):
        COMMAND_ADAPTER.validate_python(dict(action='execute_sql', request_id=str(uuid4())))
    with pytest.raises(ValidationError):
        Allocation.model_validate(dict(loan_id=str(uuid4()), expected_version=1, amount=1.0))


def test_disabled_readiness_without_owner_or_balance(monkeypatch):
    from gilbic_backend.treasury_authorization import readiness

    monkeypatch.delenv('SPINA_TREASURY_ENABLED', raising=False)
    monkeypatch.delenv('SPINA_EMPLOYEE_OWNER_USER_ID', raising=False)
    assert readiness() == {'enabled':False, 'owner_configured':False,
                           'blockers':['Treasury entry is disabled.', 'Owner identity is not configured.']}
