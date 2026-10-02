import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {createCollectorWriteGuard} from '../assets/collector-write-guard.js';
import {mountCollectorWorkflows} from '../assets/collector-workflows.js';

const regular={route_entry_id:'r',loan_id:'regular',client_id:'client',client_name:'Client',loan_type:'Regular',route_revision:'v1',can_enter_payment:true};
const seven={...regular,route_entry_id:'s',loan_id:'seven',loan_type:'7x7'};
const preview={status:'short',requires_review:true,extra_choice_required:false,allocation_order:['seven_by_seven','regular'],allocation_hash:'a'.repeat(64),cash_received_amount:'175.01',expected_total_amount:'250.00',short_amount:'74.99',extra_amount:'0.00',regular_past_due_followup_required:true,legs:[{loan_id:'seven',route_entry_id:'s',route_revision:'v1',loan_type:'seven_by_seven',collectible_amount:'50.00',scheduled_amount:'50.00',extra_amount:'0.00',total_amount:'50.00',projected_covered_dates:[]},{loan_id:'regular',route_entry_id:'r',route_revision:'v1',loan_type:'regular',collectible_amount:'200.00',scheduled_amount:'125.01',extra_amount:'0.00',total_amount:'125.01',projected_covered_dates:[]}]};
const accepted=options=>({status:'accepted',client_transaction_id:options.body.client_transaction_id,receipt_number:'receipt',total_amount:options.body.cash_received_amount,legs:(options.body.legs || []).map(leg=>({loan_id:leg.loan_id,receipt_number:'receipt'}))});
function harness({entries=[regular,seven],response=(path,options)=>path.endsWith('/combined') ? accepted(options) : preview,permissions=['collection.create','collection.correct.own_unremitted']}={}) {
  const root=new Element();const calls=[];const sequenceCounts=[];let saved=0;
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=mountCollectorWorkflows({root,api:{request:async(path,options)=>{calls.push({path,options});return response(path,options);}},session:{permissions},entries,routeDate:'2026-09-28',guard,identity:(count=1)=>{sequenceCounts.push(count);return {deviceId:'web',deviceSequence:9,clientTransactionId:'11111111-2222-4333-8444-555555555555'};},onSaved:async()=>{saved++;}});
  return {root,calls,guard,dispose,sequenceCounts,get saved(){return saved;}};
}
const set=(form,name,value)=>{form.querySelector(`[name="${name}"]`).value=value;};
const flush=async()=>{await setImmediate();await setImmediate();};
test('mounted Combined Pay reviews server split then posts same UUID/hash and promise',async()=>{
  const h=harness();const form=h.root.querySelector('[data-combined-form]');
  set(form,'amount','175.01');set(form,'reasonCode','promised_to_pay_later');set(form,'promiseDate','2026-09-29');set(form,'promiseAmount','74.99');
  fire(form.querySelector('[data-preview]'),'click');await flush();
  assert.deepEqual(h.sequenceCounts,[3]);assert.equal(form.querySelector('[data-combined-save]').disabled,false);
  assert.match(form.querySelector('[data-combined-preview]').textContent,/7x7/);assert.match(form.querySelector('[data-combined-preview]').textContent,/125\.01/);
  fire(form,'submit');await flush();
  assert.equal(h.calls[1].path,'/api/v1/collector/collections/combined');assert.equal(h.calls[1].options.financial,true);assert.equal(h.calls[1].options.body.reviewed_allocation_hash,'a'.repeat(64));
  assert.equal(h.calls[1].options.body.client_transaction_id,h.calls[0].options.body.client_transaction_id);assert.equal(h.calls[1].options.body.regular_past_due_followup.promised_amount,'74.99');assert.equal(h.saved,1);h.dispose();h.guard.dispose();
});
test('editing a reviewed form blocks direct submit until another preview',async()=>{
  const h=harness({response:()=>({...preview,regular_past_due_followup_required:false})});const form=h.root.querySelector('[data-combined-form]');set(form,'amount','175.01');
  fire(form.querySelector('[data-preview]'),'click');await flush();set(form,'amount','200');fire(form,'input');fire(form,'submit');await flush();
  assert.equal(h.calls.length,1);assert.equal(form.querySelector('[data-combined-save]').disabled,true);assert.match(h.root.textContent,/Preview the current/);h.dispose();h.guard.dispose();
});
test('mounted advance uses selected saved installment dates, not a daily multiplication',async()=>{
  const h=harness({entries:[regular],response:(path,options)=>options?.method==='POST' ? accepted(options) : ({rows:[{kind:'installment',date:'2026-09-29',remaining_amount:'100.00'},{kind:'installment',date:'2026-09-30',remaining_amount:'100.01'},{kind:'no_collection',date:'2026-10-01',remaining_amount:'0.00'}]})});
  fire(h.root.querySelector('[data-load-schedule]'),'click');await flush();const form=h.root.querySelector('[data-dates-form]');set(form,'amount','200.01');
  for(const input of form.querySelectorAll('[name="coveredDate"]'))input.checked=true;
  fire(form,'submit');await flush();assert.equal(h.calls[1].options.body.entry_type,'advance');assert.equal(h.calls[1].options.body.amount,'200.01');assert.deepEqual(h.calls[1].options.body.covered_dates,['2026-09-29','2026-09-30']);assert.equal(h.saved,1);h.dispose();h.guard.dispose();
});
test('correction is permission scoped and retains exact revision and covered dates',async()=>{
  const entry={...regular,can_enter_payment:false,processed_today:true,can_edit_today:true,today_transaction_id:'txn',today_entry_type:'payment',today_amount:'40.01',today_covered_dates:['2026-09-28']};
  const blocked=harness({entries:[entry],permissions:['collection.create']});assert.equal(blocked.root.querySelector('[data-load-schedule]'),null);blocked.dispose();blocked.guard.dispose();
  const h=harness({entries:[entry],response:(path,options)=>options?.method==='PATCH' ? {transaction_id:'txn',route_revision:'v2'} : {rows:[]}});fire(h.root.querySelector('[data-load-schedule]'),'click');await flush();const form=h.root.querySelector('[data-dates-form]');
  set(form,'entryType','payment');set(form,'amount','50.01');set(form,'reason','Correct count');form.querySelector('[name="coveredDate"]').checked=true;
  fire(form,'submit');await flush();assert.equal(h.calls[1].options.method,'PATCH');assert.equal(h.calls[1].options.body.expected_route_revision,'v1');assert.equal(h.calls[1].options.body.amount,'50.01');assert.equal(h.saved,1);h.dispose();h.guard.dispose();
});

test('null financial success and HTTP500 require authoritative refresh before another write',async()=>{
  for(const failure of ['null','500']) {
    const h=harness({response:path=>{if(path.endsWith('/preview'))return {...preview,regular_past_due_followup_required:false};if(failure==='null')return null;throw Object.assign(new Error('Internal server error'),{status:500});}});
    const form=h.root.querySelector('[data-combined-form]');set(form,'amount','175.01');fire(form.querySelector('[data-preview]'),'click');await flush();fire(form,'submit');await flush();
    assert.equal(h.guard.locked,true);assert.equal(h.saved,0);assert.equal(h.calls.length,2);
    fire(form,'submit');await flush();assert.equal(h.calls.length,2);h.dispose();h.guard.dispose();
  }
});

test('readonly preview failure stays editable and performs no financial write',async()=>{
  const h=harness({response:()=>{throw Object.assign(new Error('Preview unavailable'),{status:500});}});
  const form=h.root.querySelector('[data-combined-form]');set(form,'amount','100');fire(form.querySelector('[data-preview]'),'click');await flush();
  assert.equal(h.guard.locked,false);assert.equal(h.guard.begin(),true);h.guard.finish();assert.equal(h.calls.length,1);assert.equal(form.querySelector('[data-combined-save]').disabled,true);h.dispose();h.guard.dispose();
});
test('late preview and detached forms cannot submit after workspace disposal',async()=>{
  let resolve;const h=harness({response:()=>new Promise(done=>{resolve=done;})});const form=h.root.querySelector('[data-combined-form]');set(form,'amount','100');fire(form.querySelector('[data-preview]'),'click');h.dispose();resolve(preview);await flush();fire(form,'submit');await flush();assert.equal(h.calls.length,1);h.guard.dispose();
});

test('changed authoritative route invalidates a mounted reviewed Combined Pay without remounting its cash field',async()=>{
  const root=new Element(),guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock(){}});let consumer,posts=0;const entries=[regular,seven];let route={route_date:'2026-09-28',entries};
  const cleanup=mountCollectorWorkflows({root,api:{request:async(path,options)=>{if(path.endsWith('/preview'))return {...preview,regular_past_due_followup_required:false};posts++;return accepted(options);}},session:{permissions:['collection.create']},getSession:()=>({permissions:['collection.create']}),entries,routeDate:route.route_date,getRoute:()=>route,registerRouteConsumer:callback=>{consumer=callback;return ()=>consumer=null;},guard,identity:()=>({deviceId:'web',deviceSequence:9,clientTransactionId:'11111111-2222-4333-8444-555555555555'}),onSaved:async()=>{}});
  const form=root.querySelector('[data-combined-form]'),cash=form.querySelector('[name="amount"]');cash.value='175.01';fire(form.querySelector('[data-preview]'),'click');await flush();assert.equal(form.querySelector('[data-combined-save]').disabled,false);
  route={...route,entries:[{...regular,route_revision:'v2'},seven]};assert.equal(typeof consumer,'function');consumer(route);fire(form,'submit');await flush();assert.equal(posts,0);assert.strictEqual(form.querySelector('[name="amount"]'),cash);assert.equal(cash.value,'175.01');assert.match(root.textContent,/Route changed/);cleanup();assert.equal(consumer,null);guard.dispose();
});
