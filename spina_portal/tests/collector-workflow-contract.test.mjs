import test from 'node:test';
import assert from 'node:assert/strict';

const workflow = await import('../assets/collector-workflow-contract.js').catch(() => ({}));
const regular = {route_entry_id:'route-r', client_id:'client', loan_id:'regular', loan_type:'Regular', route_revision:'r1', can_enter_payment:true};
const seven = {...regular, route_entry_id:'route-s', loan_id:'seven', loan_type:'7x7'};
const identity = {routeDate:'2026-09-28', deviceId:'web-device', deviceSequence:4, clientTransactionId:'11111111-2222-4333-8444-555555555555', recordedAt:'2026-09-28T03:00:00Z'};
const validPreview = (overrides={}) => ({status:'exact',requires_review:false,allocation_hash:'a'.repeat(64),cash_received_amount:'100.00',expected_total_amount:'100.00',short_amount:'0.00',extra_amount:'0.00',extra_choice_required:false,regular_past_due_followup_required:false,allocation_order:['seven_by_seven','regular'],legs:[regular,seven].map(entry=>({loan_id:entry.loan_id,route_entry_id:entry.route_entry_id,route_revision:entry.route_revision,loan_type:entry===regular?'regular':'seven_by_seven',collectible_amount:'50.00',scheduled_amount:'50.00',extra_amount:'0.00',total_amount:'50.00',projected_covered_dates:[]})),...overrides});

test('combined request sends one cash total and two route references, never a client split', () => {
  const result = workflow.buildCombinedSubmission({...identity, entries:[regular,seven], amount:'250.01'});
  assert.equal(result.body.cash_received_amount,'250.01');
  assert.equal(result.headers['Idempotency-Key'],identity.clientTransactionId);
  assert.deepEqual(result.body.legs,[{route_entry_id:'route-r',loan_id:'regular',route_revision:'r1'},{route_entry_id:'route-s',loan_id:'seven',route_revision:'r1'}]);
  assert.equal(result.body.client_id,'client');
  assert.equal(result.body.reviewed_allocation_hash,undefined);
});

test('combined rejects mixed clients, missing revisions, processed rows and unsupported choices', () => {
  for (const entries of [[regular,{...seven,client_id:'other'}],[regular,{...seven,route_revision:''}],[regular,{...seven,processed_today:true}],[regular,regular]]) {
    assert.throws(()=>workflow.buildCombinedSubmission({...identity,entries,amount:'100'}));
  }
  assert.throws(()=>workflow.buildCombinedSubmission({...identity,entries:[regular,seven],amount:'100',extraChoice:'voluntary_extra'}));
});

test('combined preview is invalidated on edit and preserves identity when reviewed', async () => {
  const calls=[];
  const review=workflow.createCombinedReview({request:async(path,options)=>{calls.push({path,options});return validPreview();}});
  const draft=workflow.buildCombinedSubmission({...identity,entries:[regular,seven],amount:'100'});
  await review.preview(draft);
  const accepted=review.submission();
  assert.equal(accepted.body.client_transaction_id,identity.clientTransactionId);
  assert.equal(accepted.body.reviewed_allocation_hash,'a'.repeat(64));
  assert.equal(calls[0].path,'/api/v1/collector/collections/combined/preview');
  review.invalidate();
  assert.throws(()=>review.submission(),/preview/i);
});

test('late preview cannot restore an edited form or accept missing server review', async () => {
  let resolve;
  const review=workflow.createCombinedReview({request:()=>new Promise(done=>{resolve=done;})});
  const pending=review.preview(workflow.buildCombinedSubmission({...identity,entries:[regular,seven],amount:'100'}));
  review.invalidate();resolve({allocation_hash:'a'.repeat(64),extra_choice_required:false});
  assert.equal(await pending,null);
  assert.throws(()=>review.submission());
});

test('server requests for extra allocation or followup block combined posting', async () => {
  for(const flags of [{status:'extra_choice_required',requires_review:true,extra_choice_required:true},{regular_past_due_followup_required:true}]) {
    const review=workflow.createCombinedReview({request:async()=>validPreview(flags)});
    await review.preview(workflow.buildCombinedSubmission({...identity,entries:[regular,seven],amount:'100'}));
    assert.throws(()=>review.submission());
  }
});

test('malformed or unrelated server previews never enable confirmation', async () => {
  const invalid = [
    {status:'unknown'}, {requires_review:undefined}, {extra_choice_required:'false'}, {regular_past_due_followup_required:undefined},
    {cash_received_amount:'100.01'}, {cash_received_amount:100}, {expected_total_amount:'not-money'},
    {allocation_order:['regular','seven_by_seven']}, {extra_allocation_choice:'regular_advance'},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,loan_id:'foreign'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,route_entry_id:'foreign'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,route_revision:'changed'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,loan_type:'regular'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,total_amount:'0.00'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,scheduled_amount:'50.001'} : leg)},
    {legs:validPreview().legs.map((leg,index)=>index ? {...leg,projected_covered_dates:['bad-date']} : leg)},
    {legs:[]},
  ];
  for(const overrides of invalid) {
    const review=workflow.createCombinedReview({request:async()=>validPreview(overrides)});
    await assert.rejects(review.preview(workflow.buildCombinedSubmission({...identity,entries:[regular,seven],amount:'100'})));
    assert.throws(()=>review.submission(),/Preview/i);
  }
});

test('review money display retains every server cent without Number conversion', () => {
  assert.equal(workflow.formatServerMoney('1000000000000000.01'),'₱1,000,000,000,000,000.01');
  assert.equal(workflow.formatServerMoney('0.00'),'₱0.00');
  assert.throws(()=>workflow.formatServerMoney(100));
});

test('correction keeps exact server revision and requires own editable transaction', () => {
  const entry={...regular,today_transaction_id:'transaction',can_edit_today:true};
  const result=workflow.buildCorrection({entry,entryType:'payment',amount:'100.01',coveredDates:['2026-09-28'],reason:'Amount entered incorrectly',note:'Cash counted'});
  assert.equal(result.body.amount,'100.01');assert.equal(result.body.expected_route_revision,'r1');
  assert.equal(result.path,'/api/v1/collector/collections/transaction');
  assert.throws(()=>workflow.buildCorrection({entry:{...entry,can_edit_today:false},entryType:'pass',reason:'mistake'}));
  assert.throws(()=>workflow.buildCorrection({entry,entryType:'payment',amount:'10',coveredDates:[],reason:'mistake'}),/date/i);
});

test('schedule picker contains only authoritative remaining installment dates', () => {
  assert.deepEqual(workflow.selectableScheduleDates({rows:[{kind:'installment',date:'2026-09-28',remaining_amount:'0.01'},{kind:'installment',date:'2026-09-29',remaining_amount:'0.00'},{kind:'no_collection',date:'2026-09-30',remaining_amount:'50.00'}]}),[{date:'2026-09-28',amount:'0.01'}]);
});
