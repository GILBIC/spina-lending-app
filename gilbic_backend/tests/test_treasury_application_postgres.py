"""Full service phases + actual protected Regular/7x7 posting, never a fake adapter."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,date,datetime
from uuid import UUID,uuid4

import pytest

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_claims import upload_evidence
from gilbic_backend.treasury_models import AccountConfigure,ReceiptVerify,AllocationPreview,ReceiptApply,ReceiptApplicationReverse
from gilbic_backend.treasury_repository import TreasuryService
from gilbic_backend import treasury_collection_posting as adapter
from test_combined_collection_renewal_workflow_postgres import _setup_combined_case,DATABASE_URL
from treasury_test_support import connect,PDF

pytestmark=pytest.mark.skipif(not DATABASE_URL,reason='Explicit disposable database required')


@pytest.fixture
def real_service(monkeypatch,tmp_path):
    # Guard before invoking historical helpers, whose activation repository uses
    # application Settings; pin both paths to this exact synthetic database.
    with connect():
        pass
    monkeypatch.setenv('GILBIC_DATABASE_URL',DATABASE_URL)
    from gilbic_backend.config import get_settings
    get_settings.cache_clear()
    case=_setup_combined_case(verified_regular_schedule=True,verified_seven_schedule=True)
    actor=AccountContext(case.collector_id,case.collector_id,'synthetic',None,'Synthetic collector','active',('collector',),('collection.create','treasury.payment.apply'),True,case.device_id)
    monkeypatch.setenv('SPINA_TREASURY_ENABLED','true')
    monkeypatch.setenv('SPINA_EMPLOYEE_OWNER_USER_ID',str(actor.user_id))
    monkeypatch.setattr(adapter.combined,'_current_business_date',lambda:date(2097,8,2))
    service=TreasuryService(connect,PrivateEvidenceStore(tmp_path/'private'),clock=lambda:datetime(2097,8,3,tzinfo=UTC))
    account_id=uuid4()
    service.execute(actor,AccountConfigure(action='account_configure',request_id=uuid4(),account_id=account_id,expected_version=0,
        ledger_context_id=uuid4(),context='synthetic',kind='gcash',alias='Synthetic source wallet',ownership='synthetic',custodian_user_id=actor.user_id))
    evidence=upload_evidence(service,actor,uuid4(),account_id,'recipient',PDF,'application/pdf')['target_id']
    received=service.execute(actor,ReceiptVerify(action='receipt_verify',request_id=uuid4(),account_id=account_id,expected_version=1,
        client_id=case.client_id,amount='2000.00',provider='gcash',reference=uuid4().hex,effective_at=datetime(2097,8,2,tzinfo=UTC),
        evidence_id=evidence,recipient_attestation='Actual synthetic recipient-side verification'))
    with connect() as conn:
        loans=conn.execute('select loan_id,state_version from lending.loan_collection_state where loan_id=any(%s) order by loan_id',
            ([case.regular_loan_id,case.seven_loan_id],)).fetchall()
    reviewed=AllocationPreview(mode='combined',total_amount='100.00',loans=[{'loan_id':row['loan_id'],'expected_version':row['state_version']} for row in loans],
                              effective_date=date(2097,8,2),expected_version=1)
    preview=service.preview_receipt_application(actor,UUID(received['target_id']),reviewed)
    assert preview['can_apply'],preview
    command=ReceiptApply(**reviewed.model_dump(),action='receipt_apply',request_id=uuid4(),account_id=account_id,receipt_id=received['target_id'],digest=preview['digest'])
    return service,actor,case,received,command


def test_verified_then_failed_application_preserves_received_unapplied(real_service):
    service,actor,case,received,command=real_service
    with pytest.raises(TreasuryConflict):
        service.execute(actor,command.model_copy(update={'digest':'0'*64}))
    assert service.request_result(actor,UUID(received['request_id']))==received
    assert service.receipt_detail(actor,UUID(received['target_id']))['remaining_amount']=='2000.00'
    with connect() as conn:
        assert conn.execute('select count(*) as n from lending.collection_transactions where funding_receipt_id=%s',(received['target_id'],)).fetchone()['n']==0


def test_actual_combined_service_application_and_reversal_have_no_second_wallet_delta(real_service):
    service,actor,case,received,command=real_service
    result=service.execute(actor,command)
    assert result['result']['receipt']['applied_amount']=='100.00'
    assert result['result']['receipt']['remaining_amount']=='1900.00'
    assert service.execute(actor,command)==result
    with connect() as conn:
        assert conn.execute('select count(*) as n from lending.collection_transactions where funding_receipt_id=%s',(received['target_id'],)).fetchone()['n']==2
        assert conn.execute('select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s',(command.account_id,)).fetchone()['amount']==2000
    reversed_result=service.execute(actor,ReceiptApplicationReverse(action='receipt_application_reverse',request_id=uuid4(),account_id=command.account_id,
        expected_version=2,receipt_id=command.receipt_id,application_id=result['result']['application_id'],reason='Protected synthetic allocation correction, no provider refund'))
    assert reversed_result['result']['receipt']['remaining_amount']=='2000.00'
    assert reversed_result['result']['receipt']['refunded_amount']=='0.00'
    with connect() as conn:
        assert conn.execute('select count(*) as n from lending.collection_transactions where funding_receipt_id=%s and not is_voided',(received['target_id'],)).fetchone()['n']==0
        assert conn.execute('select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s',(command.account_id,)).fetchone()['amount']==2000


def test_two_concurrent_real_applications_same_request_replay_one_official_pair(real_service):
    service,actor,case,received,command=real_service
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(service.execute,actor,command) for _ in range(2)]
    results=[future.result() for future in futures]
    assert results[0]==results[1]
    with connect() as conn:
        assert conn.execute('select count(*) as n from lending.collection_transactions where funding_receipt_id=%s',(received['target_id'],)).fetchone()['n']==2
        assert conn.execute('select applied_amount from treasury.receipts where id=%s',(received['target_id'],)).fetchone()['applied_amount']==100


def test_downstream_second_component_failure_rolls_back_service_audit_application_outcome(real_service,monkeypatch):
    service,actor,case,received,command=real_service
    original=adapter.ConcurrentReceiptSafeCollectionPostingBridge.post_collection
    count=[]
    def fail_second(self,conn,posting_actor,posting):
        count.append(posting.loan_id)
        if len(count)==2:
            raise RuntimeError('Synthetic downstream second leg failure')
        return original(self,conn,posting_actor,posting)
    monkeypatch.setattr(adapter.ConcurrentReceiptSafeCollectionPostingBridge,'post_collection',fail_second)
    with pytest.raises(RuntimeError):
        service.execute(actor,command)
    assert service.request_result(actor,command.request_id) is None
    assert service.receipt_detail(actor,command.receipt_id)['remaining_amount']=='2000.00'
    with connect() as conn:
        assert conn.execute('select count(*) as n from treasury.applications where receipt_id=%s',(command.receipt_id,)).fetchone()['n']==0
        assert conn.execute('select count(*) as n from lending.collection_transactions where funding_receipt_id=%s',(command.receipt_id,)).fetchone()['n']==0
