"""Statement observations and matches are read evidence, never new money."""
from decimal import Decimal

from psycopg.types.json import Jsonb

from .treasury_authorization import TreasuryConflict,TreasuryDenied
from .treasury_repository import account_snapshot,identity,json_value


def get_session(conn,account,reconciliation_id):
    row=conn.execute('select * from treasury.reconciliations where id=%s and account_id=%s for update',
                      (reconciliation_id,account['id'])).fetchone()
    if row is None:
        raise TreasuryDenied('The reconciliation is unavailable.')
    if row['ledger_context_id']!=account['ledger_context_id']:
        raise TreasuryDenied('The reconciliation context is unavailable.')
    return row


def preview_reconciliation(conn,account,row):
    snapshot=account_snapshot(conn,account['id'],row['cutoff'])
    observations=conn.execute('select * from treasury.observations where reconciliation_id=%s order by effective_at,id',(row['id'],)).fetchall()
    matches=conn.execute('select * from treasury.matches where reconciliation_id=%s',(row['id'],)).fetchall()
    events=conn.execute('''select e.* from treasury.events e where e.account_id=%s and %s<e.effective_at and e.effective_at<=%s
        and not exists(select 1 from treasury.event_revisions r where r.event_id=e.id and r.action='correct') order by e.effective_at,e.id''',
        (account['id'],row['coverage_start'],row['cutoff'])).fetchall()
    unmatched_rows=[str(item['id']) for item in observations if not any(match['observation_id']==item['id'] for match in matches)]
    unmatched_events=[]
    for event in events:
        components={match['component'] for match in matches if match['event_id']==event['id']}
        if 'total' not in components and ('principal' not in components or event['fee'] and 'fee' not in components):
            unmatched_events.append(str(event['id']))
    difference=None if snapshot['expected_balance'] is None else row['actual_balance']-Decimal(snapshot['expected_balance'])
    blockers=[]
    if not snapshot['available']:
        blockers.append('Opening position not supplied.')
    if not row['complete_history']:
        blockers.append('The declared statement history is incomplete.')
    if unmatched_rows:
        blockers.append('Statement observations remain unmatched.')
    if unmatched_events:
        blockers.append('Verified ledger movements remain unmatched.')
    if difference is not None and difference!=0:
        blockers.append('The observed balance differs from the expected balance; no adjustment is implied.')
    # A close can begin at the opening, or exactly after an intact earlier close.
    coverage_anchor=snapshot['opening_cutoff']
    if coverage_anchor is not None and row['coverage_start'].isoformat()!=coverage_anchor:
        preceding=conn.execute("""select 1 from treasury.reconciliations where account_id=%s and status='reconciled'
             and not requires_review and cutoff=%s and id<>%s""",(account['id'],row['coverage_start'],row['id'])).fetchone()
        if not preceding:
            blockers.append('Coverage does not begin at the opening or a valid preceding close.')
    purpose_exceptions=[str(event['id']) for event in events if event['classification']=='verified_unclassified']
    transfers=conn.execute('''select id from treasury.transfers where (source_account_id=%s or destination_account_id=%s)
        and (source_event_id is null or destination_event_id is null)''',(account['id'],account['id'])).fetchall()
    return json_value({'id':row['id'],'account_id':account['id'],'ledger_context_id':account['ledger_context_id'],
        'version':row['version'],'status':row['status'],'opening_id':snapshot['opening_id'],'movement_watermark':account['movement_watermark'],
        'coverage_start':row['coverage_start'],'cutoff':row['cutoff'],'actual_balance':row['actual_balance'],
        'expected_balance':snapshot['expected_balance'],'difference':difference,'observations':observations,'matches':matches,
        'unmatched_observation_ids':unmatched_rows,'unmatched_event_ids':unmatched_events,'blockers':blockers,
        'can_close':not blockers,'purpose_exception_event_ids':purpose_exceptions,'incomplete_transfer_ids':[item['id'] for item in transfers],
        'message':'Account reconciliation does not approve loan-purpose, destination settlement or General Ledger exceptions.'})


def reconciliation_action(service,conn,actor,account,command):
    if command.action=='reconciliation_observe':
        if command.cutoff<command.coverage_start:
            raise TreasuryConflict('The statement cutoff precedes its coverage start.')
        service.evidence(conn,account['id'],command.evidence_id,{'statement'})
        old=conn.execute('select * from treasury.reconciliations where id=%s',(command.reconciliation_id,)).fetchone()
        if old:
            raise TreasuryConflict('Retain the original observation session; use a new exact request/session or a reviewed supersession.')
        row=conn.execute('''insert into treasury.reconciliations(id,account_id,ledger_context_id,coverage_start,cutoff,actual_balance,
            evidence_id,complete_history,status,created_by) values(%s,%s,%s,%s,%s,%s,%s,%s,'in_progress',%s) returning *''',
            (command.reconciliation_id,account['id'],account['ledger_context_id'],command.coverage_start,command.cutoff,
             Decimal(command.actual_balance),command.evidence_id,command.complete_history,actor.user_id)).fetchone()
        for item in command.rows:
            if not command.coverage_start<item.effective_at<=command.cutoff:
                raise TreasuryConflict('A statement row lies outside the exact declared coverage.')
            conn.execute('''insert into treasury.observations(id,reconciliation_id,provider,reference,direction,amount,effective_at)
                values(%s,%s,%s,%s,%s,%s,%s)''',(item.id,row['id'],item.provider,item.reference,item.direction,Decimal(item.amount),item.effective_at))
        service.bump_account(conn,account['id'])
        return row['id'],row['version'],{'reconciliation':preview_reconciliation(conn,account,row)},'saved'
    row=get_session(conn,account,command.reconciliation_id)
    service.evidence(conn,account['id'],row['evidence_id'],{'statement'})
    if row['closed_at'] is not None or row['version']!=command.reconciliation_version:
        raise TreasuryConflict('The reconciliation is already closed or changed.')
    if command.action=='reconciliation_match':
        observed=conn.execute('select * from treasury.observations where id=%s and reconciliation_id=%s',
                              (command.observation_id,row['id'])).fetchone()
        event=conn.execute('select * from treasury.events where id=%s and account_id=%s',(command.event_id,account['id'])).fetchone()
        if observed is None or event is None:
            raise TreasuryDenied('The matching observation or movement is unavailable.')
        if conn.execute("select 1 from treasury.event_revisions where event_id=%s and action='correct'",(event['id'],)).fetchone():
            raise TreasuryConflict('A corrected false observation cannot match an actual transaction.')
        if not row['coverage_start']<event['effective_at']<=row['cutoff']:
            raise TreasuryConflict('The event lies outside this exact coverage interval.')
        expected=event['amount']+event['fee'] if command.component=='total' else event['fee'] if command.component=='fee' else event['amount']
        if not expected or any(observed[key]!=event[key] for key in ['provider','reference','direction']) or observed['amount']!=expected:
            raise TreasuryConflict('Match the same account/reference/direction and exact component amount; equal amount alone is insufficient.')
        if observed['effective_at']!=event['effective_at'] and not command.exception_reason:
            raise TreasuryConflict('A transaction-time exception needs a retained specific reason.')
        prior=conn.execute('select component from treasury.matches where reconciliation_id=%s and event_id=%s',(row['id'],event['id'])).fetchall()
        if any(item['component']=='total' or command.component=='total' or item['component']==command.component for item in prior):
            raise TreasuryConflict('Net/total and gross/fee representations cannot both consume one actual movement.')
        conn.execute('''insert into treasury.matches(id,reconciliation_id,observation_id,event_id,component,exception_reason)
            values(%s,%s,%s,%s,%s,%s)''',(identity(command.request_id,'match'),row['id'],observed['id'],event['id'],command.component,command.exception_reason))
        row=conn.execute('update treasury.reconciliations set version=version+1 where id=%s returning *',(row['id'],)).fetchone()
        service.bump_account(conn,account['id'])
        return row['id'],row['version'],{'reconciliation':preview_reconciliation(conn,account,row)},'saved'
    if account['movement_watermark']!=command.movement_watermark:
        raise TreasuryConflict('Movements changed after review; refresh the current reconciliation.')
    preview=preview_reconciliation(conn,account,row)
    if preview['opening_id']!=str(command.opening_id):
        raise TreasuryConflict('The evidenced opening changed after review.')
    if preview['blockers']:
        # Persist a truthful known outcome; no close or automatic variance expense.
        return row['id'],row['version'],{'reconciliation':preview,'blockers':preview['blockers']},'blocked'
    prior=None
    if command.action=='reconciliation_supersede':
        prior=get_session(conn,account,command.prior_reconciliation_id)
        if prior['closed_at'] is None or prior['status']=='superseded' or prior['cutoff']!=row['cutoff'] or prior['coverage_start']!=row['coverage_start']:
            raise TreasuryConflict('Supersede the exact retained closed coverage; do not rewrite or delete it.')
        conn.execute("update treasury.reconciliations set status='superseded' where id=%s",(prior['id'],))
    elif conn.execute("select 1 from treasury.reconciliations where account_id=%s and closed_at is not null and status<>'superseded' and cutoff=%s",
                      (account['id'],row['cutoff'])).fetchone():
        raise TreasuryConflict('This cutoff already has a closed result; a reviewed supersession is required.')
    row=conn.execute('''update treasury.reconciliations set status='reconciled',version=version+1,opening_id=%s,movement_watermark=%s,
        expected_balance=%s,difference=%s,closed_snapshot=%s,supersedes_id=%s,closed_by=%s,closed_at=now() where id=%s returning *''',
        (command.opening_id,command.movement_watermark,Decimal(preview['expected_balance']),Decimal(preview['difference']),Jsonb(preview),
          prior['id'] if prior else None,actor.user_id,row['id'])).fetchone()
    service.bump_account(conn,account['id'])
    return row['id'],row['version'],{'reconciliation':json_value(row)},'saved'
