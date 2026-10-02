from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal
from uuid import UUID,uuid4

import pytest

from gilbic_backend.treasury_authorization import TreasuryConflict,TreasuryDenied,TreasuryUnavailable
from gilbic_backend.treasury_claims import submit_claim,upload_evidence
from gilbic_backend.treasury_models import AccountGrant,ClaimMetadata,OpeningPrepare,OpeningActivate,ReceiptVerify
from gilbic_backend.treasury_repository import account_snapshot
from treasury_test_support import treasury,connect,actor,evidence,version,PDF


def test_missing_opening_is_unknown_and_exact_zero_is_evidenced(treasury):
    f=treasury
    with connect() as conn:
        assert account_snapshot(conn,f['account_id'])['expected_balance'] is None
    prepared=f['service'].execute(f['owner'],OpeningPrepare(action='opening_prepare',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        cutoff=datetime(2026,10,1,tzinfo=timezone.utc),amount='0.00',evidence_id=evidence(f,'opening'),reason='Actual synthetic count'))
    f['service'].execute(f['owner'],OpeningActivate(action='opening_activate',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        opening_id=prepared['target_id'],opening_version=prepared['version'],confirmed=True,reason='Activate synthetic evidenced zero'))
    with connect() as conn:
        assert account_snapshot(conn,f['account_id'])['expected_balance']=='0.00'


def receipt(f,request_id=None,reference='000001',amount='1000.00',effective_at=None):
    return ReceiptVerify(action='receipt_verify',request_id=request_id or uuid4(),account_id=f['account_id'],expected_version=version(f),
        client_id=f['client_id'],amount=amount,provider='gcash',reference=reference,
        effective_at=effective_at or datetime(2026,10,2,tzinfo=timezone.utc),evidence_id=evidence(f),recipient_attestation='Checked recipient side history')


def test_duplicate_external_receipt_once_and_unchanged_recovery(treasury):
    f=treasury
    command=receipt(f)
    result=f['service'].execute(f['owner'],command)
    assert f['service'].execute(f['owner'],command)==result
    assert f['service'].request_result(f['owner'],command.request_id)==result
    # Different request/reviewer evidence can link the same verified identity.
    duplicate=f['service'].execute(f['owner'],receipt(f))
    assert duplicate['target_id']==result['target_id']
    with connect() as conn:
        assert conn.execute('select count(*) as n from treasury.events where account_id=%s',(f['account_id'],)).fetchone()['n']==1
        assert conn.execute('select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s',(f['account_id'],)).fetchone()['amount']==Decimal('1000.00')
    with pytest.raises(TreasuryConflict):
        f['service'].execute(f['owner'],command.model_copy(update={'amount':'999.00'}))


def test_two_requests_race_one_reference_and_revoked_replay_denied(treasury):
    f=treasury
    commands=[receipt(f),receipt(f)]
    # Same original version intentionally forces one account conflict, never two movements.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(f['service'].execute,f['owner'],command) for command in commands]
    saved=[]
    for future in futures:
        try:
            saved.append(future.result())
        except TreasuryConflict:
            pass
    assert len(saved)==1
    with connect() as conn:
        assert conn.execute('select count(*) as n from treasury.events where account_id=%s',(f['account_id'],)).fetchone()['n']==1
        conn.execute("update core.devices set status='revoked' where id=%s",(f['owner'].registered_device_id,))
    with pytest.raises(TreasuryDenied):
        f['service'].request_result(f['owner'],UUID(saved[0]['request_id']))


def test_claim_upload_is_own_evidence_only_and_digest_recovery(treasury):
    f=treasury
    metadata=ClaimMetadata(request_id=uuid4(),account_id=f['account_id'],account_version=version(f),client_id=f['client_id'],loan_ids=[f['loan_id']],
        amount='400.00',reference='000007',claimed_at=datetime(2026,10,2,tzinfo=timezone.utc),sender_note='A relative paid')
    result=submit_claim(f['service'],f['client_actor'],metadata,PDF,'application/pdf')
    assert submit_claim(f['service'],f['client_actor'],metadata,PDF,'application/pdf')==result
    assert result['result']['claim']['official_payment_posted'] is False
    with connect() as conn:
        assert conn.execute('select count(*) as n from treasury.events where account_id=%s',(f['account_id'],)).fetchone()['n']==0
    with pytest.raises(TreasuryConflict):
        submit_claim(f['service'],f['client_actor'],metadata,PDF.replace(b'Synthetic',b'Alternate'),'application/pdf')
    with connect() as conn:
        outsider=actor(conn,'client')
    with pytest.raises(TreasuryDenied):
        submit_claim(f['service'],outsider,metadata.model_copy(update={'request_id':uuid4()}),PDF,'application/pdf')


def test_management_role_does_not_bypass_account_or_private_history(treasury):
    f=treasury
    with connect() as conn:
        other=actor(conn)
    with pytest.raises(TreasuryDenied):
        f['service'].list_records(other,f['account_id'],'events')
    f['service'].execute(f['owner'],AccountGrant(action='account_grant',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        user_id=other.user_id,permissions=['treasury.view'],private_history=False))
    # No live role permission is seeded by configuring account access.
    with pytest.raises(TreasuryDenied):
        f['service'].list_records(other,f['account_id'],'events')


def test_disabled_entry_preserves_existing_balance_and_history(treasury,monkeypatch):
    f=treasury
    result=f['service'].execute(f['owner'],receipt(f))
    monkeypatch.setenv('SPINA_TREASURY_ENABLED','false')
    with pytest.raises(TreasuryUnavailable):
        f['service'].execute(f['owner'],receipt(f,reference='000002'))
    assert f['service'].request_result(f['owner'],UUID(result['request_id']))==result
    assert f['service'].list_records(f['owner'],f['account_id'],'events')['total_count']==1
