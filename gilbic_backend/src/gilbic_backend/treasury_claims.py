"""Private claim versions stay evidence-only; recipient receipt and application are separate transactions."""
from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from .office_review_evidence_storage import validate_evidence_content
from .treasury_authorization import (TreasuryConflict,TreasuryDenied,TreasuryUnavailable,
    is_owner,require_account,require_actor,require_borrower,require_entry)
from .treasury_models import command_hash
from .treasury_repository import identity,json_value


def claim_scope(conn, actor, claim):
    require_borrower(conn,actor,claim['client_id'],[],staff_permission='treasury.proof.review',account_id=claim['account_id'])


def get_claim(service, conn, actor, claim_id):
    claim=conn.execute('select * from treasury.claims where id=%s',(claim_id,)).fetchone()
    if claim is None:
        raise TreasuryDenied('The claim is unavailable.')
    # Assigned submitters can inspect their own assisted claim under the submit grant;
    # review is a distinct permission, and borrower assignment remains current.
    try:
        claim_scope(conn,actor,claim)
    except TreasuryDenied:
        if claim['submitted_by'] != actor.user_id:
            raise
        require_borrower(conn,actor,claim['client_id'],[],staff_permission='treasury.proof.submit.assigned',account_id=claim['account_id'])
    versions=conn.execute('''select v.*,e.sha256,e.media_type,e.byte_count from treasury.claim_versions v
        join treasury.evidence e on e.id=v.evidence_id where claim_id=%s order by version desc''',(claim_id,)).fetchall()
    if not versions:
        raise TreasuryConflict('The claim version is incomplete.')
    current=versions[0]
    service.evidence(conn,claim['account_id'],current['evidence_id'],{'claim'})
    reviews=conn.execute('select * from treasury.claim_reviews where claim_id=%s order by created_at,id',(claim_id,)).fetchall()
    result=dict(claim,current_version=current,history=versions,reviews=reviews,official_payment_posted=False)
    if claim['receipt_id']:
        receipt=conn.execute('select * from treasury.receipts where id=%s',(claim['receipt_id'],)).fetchone()
        result['receipt']=dict(receipt,remaining_amount=receipt['amount']-receipt['applied_amount']-receipt['refunded_amount'])
        applications=conn.execute("select * from treasury.applications where receipt_id=%s and status='active' order by created_at,id",(receipt['id'],)).fetchall()
        result['applications']=[{'id':row['id'],'amount':row['amount'],'transaction_ids':row['source_result'].get('transaction_ids',[])} for row in applications]
        result['official_payment_posted']=bool(applications)
    return json_value(result)


def list_claims(service, conn, actor, account_id=None, client_id=None, limit=50, offset=0):
    query='select * from treasury.claims'
    params=()
    if account_id:
        query+=' where account_id=%s'
        params=(account_id,)
    if client_id:
        require_borrower(conn,actor,client_id,[],staff_permission='treasury.proof.submit.assigned',account_id=account_id) if account_id else None
        query+=(' and' if account_id else ' where')+' client_id=%s'
        params+= (client_id,)
    # All authorized server records determine count, not merely loaded pages.
    candidates=conn.execute(query+' order by created_at,id',params).fetchall()
    items=[]
    for claim in candidates:
        try:
            items.append(get_claim(service,conn,actor,claim['id']))
        except TreasuryDenied:
            continue
    return {'items':items[offset:offset+limit],'total_count':len(items),'limit':limit,'offset':offset,
            'has_more':offset+limit<len(items),'totals':None}


def put_evidence(service, conn, actor, account, evidence_id, purpose, content, media_type):
    validate_evidence_content(content,media_type)
    digest=service.store.put(evidence_id,content,media_type)
    row=conn.execute('''insert into treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256)
        values(%s,%s,%s,%s,%s,%s,%s,%s) returning *''',(evidence_id,account['id'],actor.user_id,
           actor.registered_device_id,purpose,media_type,len(content),digest)).fetchone()
    return row


def submit_claim(service, actor, metadata, content, media_type, claim_id=None):
    require_entry()
    validate_evidence_content(content,media_type)
    import hashlib
    payload_hash=hashlib.sha256((command_hash(metadata)+hashlib.sha256(content).hexdigest()+media_type+str(claim_id)).encode()).hexdigest()
    with service.connect() as conn,conn.transaction():
        require_actor(conn,actor)
        conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(str(metadata.request_id),))
        account=conn.execute('select * from treasury.accounts where id=%s and active and designated_receiving for update',(metadata.account_id,)).fetchone()
        if account is None:
            raise TreasuryDenied('The receiving account is unavailable.')
        require_borrower(conn,actor,metadata.client_id,metadata.loan_ids,
                         staff_permission='treasury.proof.submit.assigned',account_id=metadata.account_id)
        replay=service.replay(conn,actor,metadata.request_id,payload_hash)
        if replay:
            return replay
        if account['version'] != metadata.account_version:
            raise TreasuryConflict('The designated recipient changed; review current payment instructions.')
        action='claim_version' if claim_id else 'claim_submit'
        if claim_id:
            claim=conn.execute('select * from treasury.claims where id=%s for update',(claim_id,)).fetchone()
            if claim is None or claim['client_id']!=metadata.client_id or claim['account_id']!=metadata.account_id:
                raise TreasuryDenied('The claim is unavailable.')
            claim_scope(conn,actor,claim) if claim['submitted_by']!=actor.user_id else None
            if metadata.expected_version!=claim['version'] or claim['receipt_id'] is not None:
                raise TreasuryConflict('This claim is stale or already received; a new correction is unavailable.')
            version=claim['version']+1
            conn.execute("update treasury.claims set version=%s,status='pending_verification' where id=%s",(version,claim_id))
        else:
            if metadata.expected_version is not None:
                raise TreasuryConflict('A new claim cannot replace an existing version.')
            claim_id=identity(metadata.request_id,'claim')
            version=1
            conn.execute('''insert into treasury.claims(id,account_id,ledger_context_id,client_id,submitted_by)
                values(%s,%s,%s,%s,%s)''',(claim_id,account['id'],account['ledger_context_id'],metadata.client_id,actor.user_id))
        evidence=put_evidence(service,conn,actor,account,identity(metadata.request_id,'claim-evidence'),'claim',content,media_type)
        recipient_snapshot={key:json_value(account[key]) for key in ['id','version','alias','kind','payment_instructions','masked_identifier']}
        conn.execute('''insert into treasury.claim_versions(id,claim_id,version,account_version,loan_ids,amount,reference,
            claimed_at,sender_note,evidence_id,recipient_snapshot,submitted_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (identity(metadata.request_id,'claim-version'),claim_id,version,metadata.account_version,metadata.loan_ids,
             Decimal(metadata.amount),metadata.reference,metadata.claimed_at,metadata.sender_note,evidence['id'],Jsonb(recipient_snapshot),actor.user_id))
        return service.save_result(conn,actor,metadata.request_id,action,account,'claim_own',payload_hash,claim_id,version,
                                   {'claim':get_claim(service,conn,actor,claim_id)})


def upload_evidence(service,actor,request_id,account_id,purpose,content,media_type):
    require_entry()
    permissions={'recipient':'treasury.receipt.verify','opening':'treasury.account.manage','statement':'treasury.reconcile','correction':'treasury.adjust'}
    if purpose not in permissions:
        raise TreasuryDenied('This evidence purpose is unavailable.')
    validate_evidence_content(content,media_type)
    import hashlib
    payload_hash=hashlib.sha256((str(account_id)+purpose+media_type+hashlib.sha256(content).hexdigest()).encode()).hexdigest()
    with service.connect() as conn,conn.transaction():
        require_actor(conn,actor)
        conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(str(request_id),))
        account=require_account(conn,actor,account_id,permissions[purpose],private=purpose=='statement')
        if purpose=='opening' and not is_owner(actor):
            raise TreasuryDenied('Only the configured owner may evidence an opening.')
        replay=service.replay(conn,actor,request_id,payload_hash)
        if replay:
            return replay
        row=put_evidence(service,conn,actor,account,identity(request_id,'evidence'),purpose,content,media_type)
        return service.save_result(conn,actor,request_id,'evidence_upload',account,permissions[purpose],payload_hash,row['id'],1,{'evidence':json_value(row)})


def receipt_for_application(conn, account, receipt_id, expected_version):
    receipt=conn.execute('''select r.*,c.kind as context from treasury.receipts r join treasury.contexts c on c.id=r.ledger_context_id
        where r.id=%s and r.account_id=%s for update of r''',(receipt_id,account['id'])).fetchone()
    if receipt is None or receipt['ledger_context_id']!=account['ledger_context_id']:
        raise TreasuryDenied('The receipt is unavailable.')
    if receipt['version']!=expected_version:
        raise TreasuryConflict('The receipt capacity changed; review a fresh allocation preview.')
    if conn.execute("select 1 from treasury.event_revisions where event_id=%s and action='correct'",(receipt['event_id'],)).fetchone():
        raise TreasuryConflict('The erroneous receipt has a retained correction and cannot fund payments.')
    return receipt


def adapter(service):
    if service.collection_adapter is None:
        from . import treasury_collection_posting
        return treasury_collection_posting
    return service.collection_adapter


def allocation_preview(service,conn,actor,account,receipt,command):
    if Decimal(command.total_amount)>receipt['amount']-receipt['applied_amount']-receipt['refunded_amount']:
        raise TreasuryConflict('This allocation exceeds the currently unapplied receipt.')
    result=adapter(service).preview_allocation(conn,actor,receipt,command)
    if not isinstance(result,dict) or not isinstance(result.get('digest'),str) or len(result['digest'])!=64:
        raise TreasuryConflict('The protected allocation preview is incomplete.')
    return json_value(dict(result,contract_version=1,actor={'user_id':str(actor.user_id),'device_id':str(actor.registered_device_id)},
        receipt_id=receipt['id'],account_id=account['id'],ledger_context_id=account['ledger_context_id'],receipt_version=receipt['version'],
        remaining_amount=receipt['amount']-receipt['applied_amount']-receipt['refunded_amount']))


def claim_action(service,conn,actor,account,command):
    if command.action=='claim_review':
        claim=conn.execute('select * from treasury.claims where id=%s and account_id=%s for update',(command.claim_id,account['id'])).fetchone()
        if claim is None:
            raise TreasuryDenied('The claim is unavailable.')
        claim_scope(conn,actor,claim)
        if claim['version']!=command.claim_version or claim['receipt_id']:
            raise TreasuryConflict('The evidence changed or already has a verified receipt.')
        current=get_claim(service,conn,actor,claim['id'])
        conn.execute('''insert into treasury.claim_reviews(id,claim_id,claim_version,decision,reason,actor_id)
            values(%s,%s,%s,%s,%s,%s)''',(identity(command.request_id,'claim-review'),claim['id'],command.claim_version,command.decision,command.reason,actor.user_id))
        conn.execute('update treasury.claims set status=%s where id=%s',(command.decision,claim['id']))
        service.bump_account(conn,account['id'])
        return claim['id'],claim['version'],{'claim':get_claim(service,conn,actor,claim['id'])},'saved'
    if command.action=='receipt_verify':
        if account['kind'] not in {'gcash','bank','physical_cash'}:
            raise TreasuryConflict('A transit account is not a designated borrower receiving account.')
        claim=None
        if command.claim_id:
            claim=conn.execute('select * from treasury.claims where id=%s and account_id=%s for update',(command.claim_id,account['id'])).fetchone()
            if claim is None or claim['client_id']!=command.client_id:
                raise TreasuryDenied('The claim is unavailable.')
            if command.claim_version!=claim['version'] or claim['status'] in {'rejected','correction_required'}:
                raise TreasuryConflict('The claim evidence changed or requires correction.')
            current=get_claim(service,conn,actor,claim['id'])
        require_borrower(conn,actor,command.client_id,[],staff_permission='treasury.receipt.verify',account_id=account['id'])
        event,new=service.record_verified_event(conn,actor,account,dict(id=identity(command.request_id,'receipt-event'),
           direction='credit',amount=Decimal(command.amount),fee=Decimal('0.00'),provider=command.provider,reference=command.reference,
           effective_at=command.effective_at,evidence_id=command.evidence_id,recipient_attestation=command.recipient_attestation,
           classification='borrower_receipt',reason=command.reason,reported_by_user_id=claim['submitted_by'] if claim else actor.user_id))
        existing=conn.execute('select * from treasury.receipts where event_id=%s for update',(event['id'],)).fetchone()
        if existing:
            if existing['client_id']!=command.client_id:
                raise TreasuryConflict('The external receipt has a conflicting borrower claim; investigation is required.')
            receipt=existing
        else:
            if not new:
                raise TreasuryConflict('The existing event requires a reviewed receipt classification.')
            receipt=conn.execute('''insert into treasury.receipts(id,event_id,account_id,ledger_context_id,client_id,amount,effective_at)
                values(%s,%s,%s,%s,%s,%s,%s) returning *''',(identity(event['id'],'receipt'),event['id'],account['id'],account['ledger_context_id'],
                  command.client_id,Decimal(command.amount),command.effective_at)).fetchone()
        if claim:
            if claim['receipt_id'] and claim['receipt_id']!=receipt['id']:
                raise TreasuryConflict('The claim already links a different recipient receipt.')
            conn.execute("update treasury.claims set status='received',receipt_id=%s where id=%s",(receipt['id'],claim['id']))
        return receipt['id'],receipt['version'],{'receipt':json_value(dict(receipt,remaining_amount=receipt['amount']-receipt['applied_amount']-receipt['refunded_amount'],
                verification='manually_verified',status='received_awaiting_recording')),'new_movement':new},'saved'
    receipt=receipt_for_application(conn,account,command.receipt_id,command.expected_version)
    if command.action=='receipt_apply':
        if Decimal(command.total_amount)>receipt['amount']-receipt['applied_amount']-receipt['refunded_amount']:
            raise TreasuryConflict('This allocation exceeds current unapplied receipt capacity.')
        # The protected adapter reserves device sequences BEFORE its locked loan
        # preview/digest checks, matching the existing collection writer lock order.
        result=adapter(service).apply_receipt(conn,actor,receipt,command)
        if not isinstance(result,dict) or result.get('status')!='recorded' or result.get('amount')!=command.total_amount or not result.get('transaction_ids'):
            raise TreasuryConflict('The protected allocation result is incomplete; no application was confirmed.')
        try:
            transaction_ids=[UUID(value) for value in result['transaction_ids']]
        except (ValueError,TypeError) as error:
            raise TreasuryConflict('The protected allocation identities are invalid.') from error
        if len(set(transaction_ids))!=len(transaction_ids):
            raise TreasuryConflict('Duplicate official application identities are invalid.')
        application_id=identity(command.request_id,'application')
        conn.execute('''insert into treasury.applications(id,receipt_id,account_id,ledger_context_id,amount,status,source_result,created_by)
            values(%s,%s,%s,%s,%s,'active',%s,%s)''',(application_id,receipt['id'],account['id'],account['ledger_context_id'],
             Decimal(command.total_amount),Jsonb(json_value(result)),actor.user_id))
        receipt=conn.execute('update treasury.receipts set applied_amount=applied_amount+%s,version=version+1 where id=%s returning *',
                              (Decimal(command.total_amount),receipt['id'])).fetchone()
    else:
        application=conn.execute('select * from treasury.applications where id=%s and receipt_id=%s for update',(command.application_id,receipt['id'])).fetchone()
        if application is None or application['status']!='active':
            raise TreasuryConflict('The application is unavailable or already reversed.')
        result=adapter(service).reverse_application(conn,actor,receipt,application,command)
        if not isinstance(result,dict) or result.get('status')!='reversed' or result.get('application_id')!=str(application['id']):
            raise TreasuryConflict('The protected application reversal was not confirmed.')
        conn.execute("update treasury.applications set status='reversed' where id=%s",(application['id'],))
        receipt=conn.execute('update treasury.receipts set applied_amount=applied_amount-%s,version=version+1 where id=%s returning *',
                             (application['amount'],receipt['id'])).fetchone()
        application_id=application['id']
    remaining=receipt['amount']-receipt['applied_amount']-receipt['refunded_amount']
    status='received' if receipt['applied_amount']==0 else 'partly_applied' if remaining else 'recorded'
    conn.execute('update treasury.claims set status=%s where receipt_id=%s',(status,receipt['id']))
    service.bump_account(conn,account['id'])
    return receipt['id'],receipt['version'],{'receipt':json_value(dict(receipt,remaining_amount=remaining,status=status)),
       'application_id':str(application_id),'application':result},'saved'
