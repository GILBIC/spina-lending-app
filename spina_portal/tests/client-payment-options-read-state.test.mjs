import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';

const ID='10000000-0000-4000-8000-000000000001';
const portfolio={loans:[{loan_id:ID,loan_number:'Synthetic Regular',loan_type_name:'Regular',status:'active',remaining_balance:'5000.00',daily_amount:'200.00'}]};
const capability={provider:'synthetic',mode:'sandbox',checkout_available:true,settlement_verification_ready:false,payment_available:true,message:'Synthetic checkout available',official_payment_rule:'Provider checkout is not an official payment.'};
const intent={intent_id:ID,status:'provider_pending',amount:'123.45',provider:'synthetic',mode:'sandbox',official_payment_posted:false};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
async function mount(t,{loans=portfolio,config=capability}={}){
 const root=new Element(),controller=new AbortController(),calls=[];let handle;
 const h={root,calls,loans,config,write:intent};
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});let value;
  if(options.method==='POST')value=h.write;
  else if(path==='/api/v1/client/loans')value=h.loans;
  else if(path==='/api/v1/client/gcash/config')value=h.config;
  else if(path==='/api/v1/activity-notifications')value=[];
  else if(path.includes('/payment-intents/'))value=intent;
  else value={};
  if(value instanceof Error)throw value;return value;
 }}};
 await mountClientWorkspace(context);h.context=context;h.handle=handle;
 t.after(()=>controller.abort());await setImmediate();return h;
}
async function open(h){await h.handle.activate('client-payment-instructions');await setImmediate();}
function draft(h){const form=h.root.querySelector('#client-gcash-form');assert.ok(form);const selected=form.querySelector('[data-gcash-select]'),amount=form.querySelector('[data-gcash-amount]');selected.checked=true;amount.value='123.45';return {form,selected,amount,button:form.querySelector('button[type="submit"]')};}
const posts=h=>h.calls.filter(call=>call.options.method==='POST');

for(const [label,config]of [['missing',{}],['null',null],['wrong boolean',{payment_available:'true'}]])test(`a ${label} GCash capability is unavailable with a local GET retry, never disabled configuration`,async t=>{
 const h=await mount(t,{config});await open(h);
 const region=h.root.querySelector('[data-client-region="gcash"]');
 assert.match(region.textContent,/configuration unavailable|gcash records unavailable/i);
 assert.doesNotMatch(region.textContent,/not connected/i);assert.equal(region.querySelector('#client-gcash-form'),null);
 const retry=region.querySelector('[data-client-retry]')||region.querySelector('[data-gcash-read-retry]');assert.ok(retry);
 h.config=capability;const before=h.calls.length;fire(retry,'click');await setImmediate();assert.ok(region.querySelector('#client-gcash-form'));
 assert.equal(h.calls.length,before+1);assert.equal(posts(h).length,0);
});

test('an explicit disabled capability and a verified empty active-loan list remain distinct',async t=>{
 const disabled=await mount(t,{config:{...capability,payment_available:false}});await open(disabled);
 assert.match(disabled.root.querySelector('[data-client-region="gcash"]').textContent,/not connected/i);
 const empty=await mount(t,{loans:{loans:[]}});await open(empty);assert.match(empty.root.querySelector('[data-client-region="gcash"]').textContent,/No active loan/);assert.equal(posts(empty).length,0);
});

test('GCash configuration arriving before loans creates the form when those loans become ready',async t=>{
 const pending=deferred(),h=await mount(t,{loans:pending.promise});await open(h);
 assert.equal(h.root.querySelector('#client-gcash-form'),null);
 pending.resolve(portfolio);await setImmediate();assert.ok(h.root.querySelector('#client-gcash-form'));
 assert.equal(h.calls.filter(call=>call.path==='/api/v1/client/gcash/config').length,1);assert.equal(posts(h).length,0);
});

test('a mounted checkout explains failed configuration, and local retry retains the form, amounts and provider intent',async t=>{
 const h=await mount(t);await open(h);const d=draft(h);fire(d.form,'submit');await setImmediate();
 const status=h.root.querySelector('[data-client-gcash-status]');assert.match(status.textContent,/provider_pending/);
 h.config=Object.assign(Error('Synthetic configuration read failed'),{status:503});await h.context.clientLoad('gcash',{refresh:true});
 const region=h.root.querySelector('[data-client-region="gcash"]');assert.match(region.textContent,/configuration unavailable/i);assert.equal(d.button.disabled,true);
 assert.strictEqual(h.root.querySelector('#client-gcash-form'),d.form);assert.strictEqual(h.root.querySelector('[data-client-gcash-status]'),status);assert.equal(d.amount.value,'123.45');assert.match(status.textContent,/provider_pending/);
 const retry=region.querySelector('[data-gcash-read-retry="gcash"]');assert.ok(retry);h.config=capability;const before=h.calls.length;fire(retry,'click');await setImmediate();
 assert.equal(h.calls.length,before+1);assert.equal(d.button.disabled,false);assert.equal(posts(h).length,1);
});

test('header refresh recovers the checkout regardless of loans/config response order and retains the draft',async t=>{
 const h=await mount(t);await open(h);const d=draft(h),pending=deferred();h.loans=pending.promise;
 const refreshing=h.handle.refreshVisible();await setImmediate();assert.equal(d.button.disabled,true);
 pending.resolve(portfolio);await refreshing;
 assert.equal(d.button.disabled,false);assert.strictEqual(h.root.querySelector('#client-gcash-form'),d.form);assert.equal(d.amount.value,'123.45');assert.equal(posts(h).length,0);
});

test('a loan read failure has a local retry while the selected checkout draft stays unavailable',async t=>{
 const h=await mount(t);await open(h);const d=draft(h);h.loans=Object.assign(Error('Synthetic loan read failed'),{status:503});await h.context.clientLoad('loans',{refresh:true});
 const region=h.root.querySelector('[data-client-region="gcash"]');assert.match(region.textContent,/Loan records unavailable/i);assert.equal(d.button.disabled,true);
 const retry=region.querySelector('[data-gcash-read-retry="loans"]');assert.ok(retry);h.loans=portfolio;const before=h.calls.length;fire(retry,'click');await setImmediate();
 assert.strictEqual(h.root.querySelector('#client-gcash-form'),d.form);assert.equal(d.amount.value,'123.45');assert.equal(d.button.disabled,false);assert.equal(h.calls.length,before+1);assert.equal(posts(h).length,0);
});

test('a failed config read and recovery during an unresolved POST cannot unlock or replace that attempt',async t=>{
 const h=await mount(t);await open(h);const d=draft(h),pending=deferred();h.write=pending.promise;fire(d.form,'submit');await setImmediate();
 const first=structuredClone(posts(h)[0].options.body);h.config=Object.assign(Error('Synthetic config failure'),{status:503});await h.context.clientLoad('gcash',{refresh:true});h.config=capability;await h.context.clientLoad('gcash',{refresh:true});
 assert.equal(d.button.disabled,true,'read recovery must not unlock the in-flight POST');d.button.disabled=false;fire(d.form,'submit');await setImmediate();assert.equal(posts(h).length,1,'the private pending guard also rejects a synthetic resubmission');
 pending.resolve(intent);await setImmediate();assert.strictEqual(h.root.querySelector('#client-gcash-form'),d.form);assert.equal(d.amount.value,'123.45');assert.deepEqual(posts(h)[0].options.body,first);
});

test('read recovery retains the immutable retry key and allocations after an uncertain checkout',async t=>{
 const h=await mount(t);await open(h);const d=draft(h);h.write=Object.assign(Error('Synthetic uncertain checkout'),{status:503});fire(d.form,'submit');await setImmediate();const first=structuredClone(posts(h)[0].options.body);
 h.config=Object.assign(Error('Synthetic config failure'),{status:503});await h.context.clientLoad('gcash',{refresh:true});h.config=capability;await h.context.clientLoad('gcash',{refresh:true});
 assert.strictEqual(h.root.querySelector('#client-gcash-form'),d.form);assert.equal(d.amount.value,'123.45');assert.equal(posts(h).length,1);
 h.write=intent;fire(d.form,'submit');await setImmediate();assert.equal(posts(h).length,2);assert.deepEqual(posts(h)[1].options.body,first);assert.match(h.root.querySelector('[data-client-gcash-status]').textContent,/not yet an official/);
});

for(const status of [401,403])test(`denied checkout ${status} clears private values and stale form handlers`,async t=>{
 const h=await mount(t);await open(h);const d=draft(h);h.write=Object.assign(Error('Synthetic access denial'),{status});
 fire(d.form,'submit');await setImmediate();assert.equal(d.amount.value,'');assert.equal(d.button.disabled,true);assert.equal(h.root.innerHTML,'');
 fire(d.form,'submit');await setImmediate();assert.equal(posts(h).length,1);
});

test('abort clears a checkout draft and a late provider response cannot populate the detached status',async t=>{
 const h=await mount(t);await open(h);const d=draft(h),pending=deferred(),status=h.root.querySelector('[data-client-gcash-status]');h.write=pending.promise;
 fire(d.form,'submit');await setImmediate();h.handle.dispose();pending.resolve(intent);await setImmediate();
 assert.equal(d.amount.value,'');assert.equal(status.innerHTML,'');assert.equal(h.root.innerHTML,'');fire(d.form,'submit');await setImmediate();assert.equal(posts(h).length,1);
});
