from datetime import datetime,timezone
from decimal import Decimal
from uuid import UUID,uuid4

import pytest

from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import AccountConfigure,DisbursementRecord,MovementCorrect,TransferRecord
from gilbic_backend.treasury_repository import account_snapshot
from treasury_test_support import treasury,connect,evidence,version
from test_treasury_reconciliation_postgres import opening,movement,T0,T1


def test_unapproved_actual_debit_remains_exception_not_paid_and_fee_once(treasury):
    f=treasury
    opening(f)
    command=DisbursementRecord(action='disbursement_record',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        amount='2000.00',fee='15.00',provider='gcash',reference='unapproved-001',effective_at=T1,evidence_id=evidence(f),
        recipient_attestation='Actually debited in the recipient history',purpose='loan_release',source_id=uuid4(),source_version=1,payee_id=f['client_id'],reason='Investigate unmatched real debit')
    result=f['service'].execute(f['owner'],command)
    assert result['result']['source_link']['status']=='blocked'
    assert result['result']['event']['status']=='debited_destination_unconfirmed'
    assert f['service'].execute(f['owner'],command)==result
    with connect() as conn:
        assert account_snapshot(conn,f['account_id'],T1)['expected_balance']=='7985.00'
        assert conn.execute('select count(*) as n from treasury.source_links where event_id=%s',(result['target_id'],)).fetchone()['n']==0


def test_actual_refund_consumes_capacity_once_without_loan_void(treasury):
    from test_treasury_postgres import receipt
    f=treasury
    opening(f)
    received=f['service'].execute(f['owner'],receipt(f))
    command=DisbursementRecord(action='disbursement_record',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        amount='200.00',provider='gcash',reference='refund-001',effective_at=T1,evidence_id=evidence(f),
        recipient_attestation='Actual refund debit independently verified',purpose='refund',receipt_id=received['target_id'],reason='Actual provider refund, not loan void')
    result=f['service'].execute(f['owner'],command)
    assert f['service'].execute(f['owner'],command)==result
    with connect() as conn:
        stored=conn.execute('select * from treasury.receipts where id=%s',(received['target_id'],)).fetchone()
        assert stored['refunded_amount']==Decimal('200.00') and stored['applied_amount']==0
        assert account_snapshot(conn,f['account_id'],T1)['expected_balance']=='10800.00'


def test_transfer_two_real_times_not_income_and_source_in_transit(treasury):
    f=treasury
    opening(f)
    other_id=uuid4()
    f['service'].execute(f['owner'],AccountConfigure(action='account_configure',request_id=uuid4(),account_id=other_id,expected_version=0,
        ledger_context_id=f['context_id'],context='synthetic',kind='bank',alias='Synthetic second account',ownership='synthetic',custodian_user_id=f['owner'].user_id))
    transfer_id=uuid4()
    first=f['service'].execute(f['owner'],TransferRecord(action='transfer_record',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        transfer_id=transfer_id,leg='source',other_account_id=other_id,other_account_version=1,amount='1000.00',provider='gcash',reference='source001',
        effective_at=T1,evidence_id=evidence(f),recipient_attestation='Source debit verified',reason='Own tracked transfer'))
    assert first['result']['transfer']['transit_amount']=='1000.00'
    from gilbic_backend.treasury_claims import upload_evidence
    from treasury_test_support import PDF
    other_evidence=upload_evidence(f['service'],f['owner'],uuid4(),other_id,'recipient',PDF,'application/pdf')['target_id']
    second=f['service'].execute(f['owner'],TransferRecord(action='transfer_record',request_id=uuid4(),account_id=other_id,expected_version=1,
        transfer_id=transfer_id,leg='destination',other_account_id=f['account_id'],other_account_version=version(f),amount='1000.00',provider='bank',reference='destination002',
        effective_at=datetime(2026,10,2,1,tzinfo=timezone.utc),evidence_id=other_evidence,recipient_attestation='Destination credit independently verified',reason='Own tracked transfer received'))
    assert second['result']['transfer']['status']=='completed' and second['result']['transfer']['transit_amount']=='0.00'
    with connect() as conn:
        assert account_snapshot(conn,f['account_id'],T1)['expected_balance']=='9000.00'
        assert conn.execute('select count(*) as n from treasury.events where account_id=any(%s)',([f['account_id'],other_id],)).fetchone()['n']==2


def test_false_observation_correction_keeps_original_reference_reserved(treasury):
    f=treasury
    opening(f)
    event=movement(f,'mistaken001','100.00')
    result=f['service'].execute(f['owner'],MovementCorrect(action='movement_correct',request_id=uuid4(),account_id=f['account_id'],expected_version=version(f),
        event_id=event['target_id'],event_version=1,evidence_id=evidence(f,'correction'),correction='false_observation',reason='Evidence proves this was not an actual debit'))
    with connect() as conn:
        assert account_snapshot(conn,f['account_id'],T1)['expected_balance']=='10000.00'
        assert conn.execute('select count(*) as n from treasury.events where id=%s',(event['target_id'],)).fetchone()['n']==1
    with pytest.raises(TreasuryConflict):
        movement(f,'mistaken001','100.00')
