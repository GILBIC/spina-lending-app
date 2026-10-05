import assert from 'node:assert/strict';
import test from 'node:test';
import { collectorControlSchedule, mountCollectorControls } from '../assets/management-collector-controls.js';
import { Element, fire } from './helpers/dom.mjs';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const book = {status:'configured',book_id:id(1),kind:'owner_operations',entity_label:'Owner book'};
const session = {user:{id:id(2),roles:['management'],role:'Management'},permissions:['accounting.view']};
const tick = () => new Promise(resolve => setImmediate(resolve));
function schedule() { return {
  book,as_of:'2026-09-30',business_timezone:'Asia/Manila',balance_basis:'debit_minus_credit',
  controls:[['1060','debit','4.00','4.00'],['2210','credit','0.00','0.00'],['2220','credit','-10.00','10.00']].map(([account_code,normal_balance,balance,amount])=>({account_code,normal_balance,source_balance:balance,ledger_balance:balance,difference:'0.00',source_amount:amount,ledger_amount:amount,unregistered_line_count:0})),
  movements:[{account_code:'2220',effective_date:'2026-09-30',signed_amount:'-10.00',source_type:'collector_credit',source_id:id(5),exact_posted:true}],
  movement_count:1,unproven_movement_count:0,correction_count:0,limit:100,offset:0,
  current_capacity:{observed_at:'2026-10-05T01:02:03+00:00',unidentified_amount:'0.00',outstanding_amount:'10.00',reserved_amount:'4.00',available_amount:'6.00'},
  controls_reconciled:true,comprehensive_source_coverage:false,
}; }
function fixture() { return { calls:[],denied:false,changedBook:false,value:schedule(),delayed:null,async request(path,options={}) {
  this.calls.push([path,options]);
  if(path.endsWith('/book')) return {book:{...book,...(this.changedBook?{book_id:id(99)}:{})}};
  if(this.denied) throw Object.assign(Error('Current private history access is required.'),{status:403});
  return this.delayed ? await this.delayed : this.value;
}}; }

test('view-only schedule distinguishes credit liabilities, debit transit and observed reservations',async()=>{
  const root=new Element(),api=fixture();await mountCollectorControls({root,api,session});
  assert.match(root.textContent,/Collector credit owed/);assert.match(root.textContent,/Returns awaiting confirmation/);
  assert.match(root.textContent,/Ledger amount: PHP 10.00/);assert.match(root.textContent,/Reserved within outstanding: PHP 4.00/);
  assert.match(root.textContent,/2026-10-05T01:02:03\+00:00/);assert.match(root.textContent,/1–1 of 1/);
  assert.ok(api.calls.every(([,options])=>!options.method||options.method==='GET'));
  assert.doesNotMatch(root.textContent,/Prepare|Confirm posting|all accounting ready/i);
});
test('projection rejects wrong normal direction, missing money and false completeness',()=>{
  for(const change of [v=>v.controls[2].normal_balance='debit',v=>v.controls[2].ledger_amount='-10.00',v=>v.current_capacity.reserved_amount=null,v=>v.comprehensive_source_coverage=true,v=>v.controls[2].unregistered_line_count=2]){const value=schedule();change(value);assert.throws(()=>collectorControlSchedule(value,id(1)));}
  const value=schedule();value.private_origin={secret:'PRIVATE'};value.movements[0].account_id=id(90);const result=collectorControlSchedule(value,id(1));assert.doesNotMatch(JSON.stringify(result),/PRIVATE|account_id/);
});
test('date change clears balances before loading another cutoff; denied refresh clears all data',async()=>{
  const root=new Element(),api=fixture();await mountCollectorControls({root,api,session});
  const input=root.querySelector('[name="as_of"]');input.value='2026-08-31';fire(input,'input');await tick();
  assert.doesNotMatch(root.textContent,/Ledger amount: PHP 10.00/);
  api.denied=true;fire(root.querySelector('[data-controls-filter]'),'submit');await tick();await tick();
  assert.doesNotMatch(root.textContent,/Owner book|PHP 10.00|00000000/);assert.match(root.textContent,/access/i);
});
test('pagination is explicit and book change rejects late totals',async()=>{
  const root=new Element(),api=fixture();api.value.movement_count=101;api.value.movements=Array.from({length:100},(_,i)=>({...api.value.movements[0],source_id:id(10+i)}));
  await mountCollectorControls({root,api,session});assert.match(root.textContent,/1–100 of 101/);assert.ok(root.querySelector('[data-controls-next]'));
  api.changedBook=true;fire(root.querySelector('[data-controls-next]'),'click');await tick();await tick();
  assert.doesNotMatch(root.textContent,/PHP 10.00|Owner book/);
});
test('session change and disposal discard delayed private response',async()=>{
  const root=new Element(),api=fixture(),controller=new AbortController();let resolve;api.delayed=new Promise(r=>resolve=r);let current=session;
  const mounting=mountCollectorControls({root,api,session,getSession:()=>current,signal:controller.signal});await tick();current={...session,access_token:'replacement'};resolve(schedule());await mounting;
  assert.doesNotMatch(root.textContent,/PHP 10.00|Owner book/);controller.abort();assert.doesNotMatch(root.textContent,/00000000/);
});
test('unknown control role cannot validate through missing normal direction',()=>{
  const value=schedule();value.controls[2].account_code='9999';delete value.controls[2].normal_balance;
  assert.throws(()=>collectorControlSchedule(value,id(1)));
});
