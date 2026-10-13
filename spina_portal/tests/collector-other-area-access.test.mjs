import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {createCollectorWriteGuard} from '../assets/collector-write-guard.js';
import {mountCollectorOtherArea} from '../assets/collector-other-area.js';

const entry={route_entry_id:'route',client_id:'client',loan_id:'loan',route_revision:'v1',client_name:'Private borrower',assigned_collector_name:'Private collector',loan_type:'Regular',can_collect_mobile:true,can_enter_payment:true,daily_amount:'100.01'};
const failure=status=>Object.assign(new Error('Request failed'),{status});
function workspace(t,request,extra={}) {
  const root=new Element();let identities=0;const calls=[];
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=mountCollectorOtherArea({root,guard,session:{permissions:['collection.create']},routeDate:'2026-09-29',identity:()=>{identities++;return {deviceId:'web',deviceSequence:identities,clientTransactionId:'11111111-2222-4333-8444-555555555555'};},onSaved:async()=>{},api:{request:async(path,options)=>{calls.push({path,options});return request(path,options);}},...extra});
  t.after(()=>{dispose();guard.dispose();});
  const search=root.querySelector('[data-other-search]');
  const input=search.querySelector('[name="query"]');input.value='Private borrower';
  return {root,guard,calls,search,input,identities:()=>identities};
}
async function findClient(w) {fire(w.search,'submit');await setImmediate();}
function preparePayment(w) {
  const form=w.root.querySelector('[data-other-payment]');
  form.querySelector('[name="amount"]').value='100.01';
  form.querySelector('[name="note"]').value='Private collection note';
  form.querySelector('[name="recorderConfirmation"]').checked=true;
  return form;
}

for(const mode of ['collector','management'])for(const status of [401,403,426]) {
  test(`${mode} search ${status} removes private data and retires detached controls`,async t=>{
    let searches=0;let unsubscribed=0;
    const w=workspace(t,async()=>{if(++searches===1)return [entry];throw failure(status);},{mode,registerRouteConsumer:()=>()=>{unsubscribed++;}});
    await findClient(w);const payment=preparePayment(w);
    await findClient(w);
    assert.match(w.root.textContent,/access is unavailable/i);
    assert.doesNotMatch(w.root.textContent,/Private borrower|Private collector|Private collection note/);
    assert.equal(w.root.querySelector('form'),null);
    assert.equal(unsubscribed,1);
    const before=w.calls.length;
    fire(payment,'submit');fire(w.search,'submit');fire(w.input,'input');await setImmediate();
    assert.equal(w.calls.length,before);assert.equal(w.identities(),0);
    assert.equal(w.guard.busy,false);
  });
}

test('other-area transient search failure retains the draft and allows a successful search',async t=>{
  let searches=0;
  const w=workspace(t,async()=>{if(++searches===2)throw failure(503);return [entry];});
  await findClient(w);const payment=preparePayment(w);
  await findClient(w);
  assert.equal(w.root.querySelector('[data-other-payment]'),payment);
  assert.equal(payment.querySelector('[name="note"]').value,'Private collection note');
  assert.equal(w.guard.locked,false);
  await findClient(w);
  assert.equal(w.calls.length,3);assert.ok(w.root.querySelector('[data-other-payment]'));
});

test('search denial fences a late remittance response',async t=>{
  let finishTargets;const targets=new Promise(resolve=>{finishTargets=resolve;});let searches=0;
  const w=workspace(t,async path=>{if(path.includes('/targets'))return targets;if(++searches===1)return [entry];throw failure(403);},{session:{permissions:['collection.create','remittance.create']}});
  await findClient(w);await findClient(w);
  finishTargets([{recipient_user_id:'owner',recipient_name:'Private recipient',recipient_capacity:'assigned_collector',role_name:'Collector',total_amount:'100.01'}]);
  await setImmediate();
  assert.equal(w.root.querySelector('form'),null);
  assert.doesNotMatch(w.root.textContent,/Private/);
});

test('remittance load denial clears an already displayed search result',async t=>{
  let rejectTargets;const targets=new Promise((resolve,reject)=>{rejectTargets=reject;});
  const w=workspace(t,async path=>path.includes('/targets')?targets:[entry],{session:{permissions:['collection.create','remittance.create']}});
  await findClient(w);const payment=preparePayment(w);
  rejectTargets(failure(426));await setImmediate();
  assert.match(w.root.textContent,/access is unavailable/i);
  assert.equal(w.root.querySelector('form'),null);
  fire(payment,'submit');await setImmediate();assert.equal(w.identities(),0);
});

test('payment denial removes private data and does not retry a detached draft',async t=>{
  const w=workspace(t,async(path,options)=>{if(options?.method==='POST')throw failure(403);return [entry];});
  await findClient(w);const payment=preparePayment(w);
  fire(payment,'submit');await setImmediate();
  assert.equal(w.root.querySelector('form'),null);assert.match(w.root.textContent,/access is unavailable/i);
  fire(payment,'submit');await setImmediate();
  assert.equal(w.calls.filter(call=>call.options?.method==='POST').length,1);
  assert.equal(w.identities(),1);
});
