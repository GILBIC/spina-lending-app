import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {mountCollectorWorkspace} from '../assets/roles/collector.js';

const note = 'Synthetic note retained until confirmed';
const finalFacts = body => ({status:'accepted',client_transaction_id:body.client_transaction_id,
  transaction_id:'synthetic-transaction',receipt_number:'SYNTHETIC-RECEIPT',
  official_balance:'750.00',accepted_at:'2026-10-09T02:30:00.000000Z'});
const variants = [
  ['missing transaction', {transaction_id:undefined}], ['blank transaction', {transaction_id:'  '}],
  ['numeric transaction', {transaction_id:123}], ['missing balance', {official_balance:undefined}],
  ['invalid balance', {official_balance:'not-money'}], ['negative balance', {official_balance:'-0.01'}],
  ['numeric balance', {official_balance:750}], ['fractional balance', {official_balance:'750.001'}],
  ['missing time', {accepted_at:undefined}], ['invalid time', {accepted_at:'yesterday'}],
  ['local time', {accepted_at:'2026-10-09T02:30:00'}],
  ['impossible date', {accepted_at:'2026-02-30T02:30:00Z'}],
  ['mismatched command', {client_transaction_id:'other-command'}], ['missing command', {client_transaction_id:undefined}],
  ['blank receipt', {receipt_number:'  '}], ['missing receipt', {receipt_number:undefined}],
  ['contradictory duplicate flag', {duplicate:true}], ['unknown status', {status:'saved'}],
];

async function workspace(t, response) {
  const original = globalThis.FormData;
  globalThis.FormData = class {constructor(form) {this.form=form;} get(name) {return this.form.querySelector(`[name="${name}"]`)?.value ?? null;}};
  t.after(()=>{globalThis.FormData=original;});
  const doc = new EventTarget(); doc.body = new Element('body'); doc.activeElement = doc.body;
  doc.createElement = tag => {const node = new Element(tag); node.ownerDocument = doc; return node;};
  const root = new Element(); root.dataset = {}; root.ownerDocument = doc;
  const controller = new AbortController(); t.after(()=>controller.abort());
  let handle; const writes = []; let reads = 0; let sequence = 0;
  const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle(value){handle=value;},
    session:{user:{role:'collector',id:'synthetic-collector'},permissions:['route.view','collection.create']},
    sessionStore:{deviceId:()=> 'synthetic-device',nextDeviceSequence:()=>++sequence},
    api:{async request(path,options={}) {
      if(options.method) {writes.push({path,options}); return response(options.body);}
      if(path==='/api/v1/collector/routes/today') {reads++; return {route_date:'2026-10-09',entries:[{route_entry_id:'route-1',client_id:'client-1',loan_id:'loan-1',client_name:'Synthetic Borrower',loan_type:'Regular',route_revision:'v1',can_enter_payment:true,daily_amount:'250.00',remaining_balance:'1000.00'}]};}
      return {};
    }}};
  await mountCollectorWorkspace(context);
  const form=root.querySelector('.collector-entry-form'); assert.ok(form); form.hidden=false;
  for(const [name,value] of Object.entries({entryType:'payment',amount:'250.00',allocation:'scheduled',note})) form.querySelector(`[name="${name}"]`).value=value;
  return {root,form,writes,handle,guard:context.collectorWriteGuard,get reads(){return reads;},get sequence(){return sequence;}};
}
const flush = async () => {await setImmediate();await setImmediate();};

for (const status of ['accepted','duplicate']) test(`real workspace confirms canonical ${status} then clears only the saved editor`,async t=>{
  const h=await workspace(t,body=>({...finalFacts(body),status,duplicate:status==='duplicate'}));
  fire(h.form,'submit');await flush();
  assert.equal(h.writes.length,1);assert.match(h.form.querySelector('[data-collection-feedback]').textContent,/^Saved\./);
  assert.equal(h.form.querySelector('[name="note"]').value,'');assert.equal(h.root.dataset.financialLocked,'false');assert.equal(h.reads,2);assert.equal(h.guard.pendingCommand,null);
  fire(h.form,'submit');await flush();assert.equal(h.writes.length,1);
});

for (const status of ['accepted','duplicate']) for (const [name,changes] of variants) {
  const overrides=status==='duplicate' && name==='contradictory duplicate flag' ? {duplicate:false} : changes;
  test(`real workspace retains draft and reconciliation lock for ${status} ${name}`,async t=>{
    const h=await workspace(t,body=>({...finalFacts(body),status,...overrides}));
    fire(h.form,'submit');await flush();
    assert.equal(h.writes.length,1,'protected POST reached');
    assert.doesNotMatch(h.form.querySelector('[data-collection-feedback]').textContent,/^Saved\./);
    assert.equal(h.form.querySelector('[name="note"]').value,note);assert.equal(h.form.querySelector('[name="amount"]').value,'250.00');
    assert.equal(h.root.dataset.financialLocked,'true');assert.equal(h.handle.isWritePending(),true);assert.equal(h.reads,1);
    const command=structuredClone(h.writes[0].options.body);
    assert.deepEqual(h.guard.pendingCommand.options.body,command);assert.equal(h.guard.pendingCommand.path,'/api/v1/collector/collections');
    await h.handle.refreshVisible();fire(h.form,'submit');fire(h.form.querySelector('.cancel-entry'),'click');await flush();
    assert.equal(h.writes.length,1);assert.equal(h.sequence,1);assert.equal(h.reads,1);
    assert.deepEqual(h.writes[0].options.body,command);assert.deepEqual(h.guard.pendingCommand.options.body,command);assert.equal(h.form.querySelector('[name="note"]').value,note);
  });
}

for(const status of ['accepted','duplicate']) test(`legitimate ${status} zero PASS has final facts without a receipt and never displays an invented receipt`,async t=>{
  const h=await workspace(t,body=>({...finalFacts(body),status,duplicate:status==='duplicate',receipt_number:null,official_balance:'0.00'}));
  h.form.querySelector('[name="entryType"]').value='pass';h.form.querySelector('[name="reasonCode"]').value='no_cash';
  fire(h.form,'submit');await flush();
  assert.equal(h.writes.length,1);assert.equal(h.writes[0].options.body.entry_type,'pass');
  assert.match(h.form.querySelector('[data-collection-feedback]').textContent,/^Saved\./);
  assert.doesNotMatch(h.form.querySelector('[data-collection-feedback]').textContent,/Receipt (null|undefined)/);
  assert.equal(h.form.querySelector('[name="note"]').value,'');assert.equal(h.root.dataset.financialLocked,'false');
});

test('lost acknowledgement retains note and pending write through ordinary recovery attempts',async t=>{
  const h=await workspace(t,()=>{throw Object.assign(new Error('Response lost'),{code:'network_uncertain'});});
  fire(h.form,'submit');await flush();await h.handle.refreshVisible();fire(h.form,'submit');await flush();
  assert.equal(h.writes.length,1);assert.equal(h.sequence,1);assert.equal(h.handle.isWritePending(),true);
  assert.deepEqual(h.guard.pendingCommand.options.body,h.writes[0].options.body);
  assert.equal(h.form.querySelector('[name="note"]').value,note);assert.equal(h.root.dataset.financialLocked,'true');
});

test('in-flight collection cannot clear its typed note through Cancel',async t=>{
  let finish;const h=await workspace(t,body=>new Promise(resolve=>{finish=()=>resolve(finalFacts(body));}));
  fire(h.form,'submit');await flush();fire(h.form.querySelector('.cancel-entry'),'click');
  assert.equal(h.form.querySelector('[name="note"]').value,note);assert.equal(h.form.hidden,false);
  assert.deepEqual(h.guard.pendingCommand.options.body,h.writes[0].options.body);
  finish();await flush();assert.match(h.form.querySelector('[data-collection-feedback]').textContent,/^Saved\./);assert.equal(h.guard.pendingCommand,null);
});

test('confirmed receipt retains large exact balance and timezone-bearing fractional timestamp',async t=>{
  const h=await workspace(t,body=>({...finalFacts(body),official_balance:'1000000000000000.01',accepted_at:'2026-10-09T10:30:00.000001+08:00'}));
  fire(h.form,'submit');await flush();assert.match(h.form.querySelector('[data-collection-feedback]').textContent,/1,000,000,000,000,000\.01/);
  assert.equal(h.guard.pendingCommand,null);assert.equal(h.root.dataset.financialLocked,'false');
});
