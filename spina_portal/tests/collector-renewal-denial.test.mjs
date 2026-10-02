import test from 'node:test';
import assert from 'node:assert/strict';
import {Element,fire} from './helpers/dom.mjs';
import {mountCollectorRenewals} from '../assets/collector-renewals.js';
import {createCollectorWriteGuard} from '../assets/collector-write-guard.js';

const session={permissions:['renewal.cash_custody.assigned']};
const item={request_id:'request-one',loan_id:'loan-one',client_name:'Private synthetic borrower',status:'approved',collector_cash_received_at:'2026-10-01',cash_given_to_client_at:'2026-10-01',handover_proof_status:'not_submitted'};
const settle=()=>new Promise(resolve=>setTimeout(resolve,0));

function fixture(t,{status=403}={}) {
  const root=new Element(),guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock(){}});
  let handle,posts=0,reads=0,denyRead=false,currentSession=session;
  const cleanup=mountCollectorRenewals({root,guard,getSession:()=>currentSession,registerHandle:value=>handle=value,onSaved:async()=>{},api:{async request(path,options){
    if(options?.method){posts++;throw Object.assign(Error('Denied synthetic renewal'),{status});}
    reads++;if(denyRead)throw Object.assign(Error('Denied synthetic queue'),{status});
    return {requests:[item]};
  }}});
  t.after(()=>{cleanup();guard.dispose();});
  return {root,guard,get handle(){return handle;},get posts(){return posts;},get reads(){return reads;},denyRead:()=>{denyRead=true;},revoke:()=>{currentSession={permissions:[]};}};
}

for(const status of [401,403])test(`denied renewal handover ${status} clears private file and prevents detached form retry`,async t=>{
  const h=fixture(t,{status});await h.handle.refresh();const retainedHandle=h.handle;
  const form=h.root.querySelector('[data-renewal-action="handover-photo"]'),photo=form.querySelector('[name="photo"]'),more=h.root.querySelector('[data-more-renewals]');
  photo.value='C:\\fakepath\\synthetic-private.jpg';photo.files=[{name:'synthetic-private.jpg',type:'image/jpeg',size:1}];
  fire(form,'submit');await settle();
  assert.doesNotMatch(h.root.textContent,/Private synthetic borrower/);
  assert.match(h.root.textContent,/access.*unavailable/i);
  assert.equal(photo.value,'');assert.equal(photo.disabled,true);assert.equal(form.querySelector('button').disabled,true);
  assert.equal(h.handle,null);assert.equal(h.guard.current,true);assert.equal(h.guard.locked,false);
  fire(form,'submit');fire(more,'click');await retainedHandle.refresh();await settle();
  assert.equal(h.posts,1);assert.equal(h.reads,1);
});

for(const status of [401,403])test(`denied renewal queue ${status} clears retained draft and preserves the financial lock`,async t=>{
  const h=fixture(t,{status});await h.handle.refresh();const retainedHandle=h.handle;
  const form=h.root.querySelector('[data-renewal-action="handover-photo"]'),photo=form.querySelector('[name="photo"]');
  photo.value='C:\\fakepath\\synthetic-private.jpg';photo.files=[{name:'synthetic-private.jpg',type:'image/jpeg',size:1}];
  h.guard.lock('Existing uncertain collection');h.denyRead();await retainedHandle.refresh();
  assert.doesNotMatch(h.root.textContent,/Private synthetic borrower/);assert.match(h.root.textContent,/access.*unavailable/i);
  assert.equal(photo.value,'');assert.equal(photo.disabled,true);assert.equal(h.handle,null);
  assert.equal(h.guard.current,true);assert.equal(h.guard.locked,true);
  fire(form,'submit');await retainedHandle.refresh();await settle();
  assert.equal(h.posts,0);assert.equal(h.reads,2);
});

test('lost renewal permission clears private draft before another queue request',async t=>{
  const h=fixture(t);await h.handle.refresh();const retainedHandle=h.handle;
  const photo=h.root.querySelector('[name="photo"]');photo.value='C:\\fakepath\\synthetic-private.jpg';
  h.revoke();await retainedHandle.refresh();
  assert.equal(photo.value,'');assert.equal(photo.disabled,true);assert.equal(h.handle,null);
  assert.match(h.root.textContent,/access.*unavailable/i);assert.equal(h.reads,1);
});

test('pending request navigation cannot reveal a queue after permission is revoked',async t=>{
  const root=new Element(),guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock(){}});
  let current=session,handle,resolve;
  const cleanup=mountCollectorRenewals({root,guard,getSession:()=>current,registerHandle:value=>handle=value,onSaved:async()=>{},api:{request:()=>new Promise(done=>resolve=done)}});
  t.after(()=>{cleanup();guard.dispose();});
  const pending=handle.openRequest(item.request_id);current={permissions:[]};resolve({requests:[item]});
  assert.equal(await pending,false);assert.equal(handle,null);
  assert.doesNotMatch(root.textContent,/Private synthetic borrower/);assert.match(root.textContent,/access.*unavailable/i);
  assert.equal(guard.current,true);assert.equal(guard.locked,false);
});

test('a normal renewal validation error retains the selected photo without automatic retry',async t=>{
  const h=fixture(t,{status:422});await h.handle.refresh();
  const form=h.root.querySelector('[data-renewal-action="handover-photo"]'),photo=form.querySelector('[name="photo"]');
  photo.value='C:\\fakepath\\synthetic-private.jpg';photo.files=[{name:'synthetic-private.jpg',type:'image/jpeg',size:1}];
  fire(form,'submit');await settle();
  assert.strictEqual(h.root.querySelector('[name="photo"]'),photo);assert.equal(photo.value,'C:\\fakepath\\synthetic-private.jpg');
  assert.match(h.root.textContent,/Private synthetic borrower/);assert.equal(h.posts,1);assert.equal(h.guard.locked,false);
});
