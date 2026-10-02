import assert from 'node:assert/strict';
import test from 'node:test';
import { fire } from './helpers/dom.mjs';
import { id, row, tick, setup, session, fill, confirm, approved } from './helpers/management-renewal-fixture.mjs';

test('rejection requires reason and sends only supported rejection fields', async () => {
  const writes = [];
  const {root, handle} = await setup({async request(path, options) {
    if (options?.method) { writes.push(options.body); return {request: {...row(), status:'rejected', review_note:options.body.review_note, reviewed_at:'2026-10-02T01:00:00Z'}}; }
    return {requests:[row()]};
  }});
  const form = fill(root, 0, {decision:'rejected', review_note:''});
  fire(form,'submit'); await tick();
  assert.equal(root.querySelector('[data-renewal-confirm-action]'), null);
  form.querySelector('[name="review_note"]').value='Borrower requested withdrawal';
  await confirm(root, form);
  assert.deepEqual(writes, [{decision:'rejected', review_note:'Borrower requested withdrawal'}]);
  assert.match(root.textContent, /Terms saved/);
  handle.dispose();
});

test('office terms use explicit reviewed identity without inventing an account or signatures', async () => {
  let written;
  const {root, handle} = await setup({async request(path, options) {
    if (options?.method) { written=options.body; const result=approved(row(), written); result.signer_readiness_status='office_required'; return {request:result}; }
    return {requests:[row()]};
  }});
  const form=fill(root,0,{office_processing_required:true});
  form.querySelector('[name="user_id"]').value='';
  await confirm(root,form);
  assert.equal(written.signers[0].user_id,null);
  assert.equal(written.signers[0].government_id_verified,false);
  assert.equal(written.signers[0].selfie_verified,false);
  assert.match(root.textContent,/office_required/);
  assert.equal(handle.isWritePending(),false);
  handle.dispose();
});

test('current actor, device and permission are rechecked after delayed preflight', async () => {
  for (const change of [s=>({...s,user:{id:id(98)}}), s=>({...s,device_id:'different'}), s=>({...s,permissions:[]})]) {
    let current=structuredClone(session), release, reads=0, posts=0;
    const {root,handle}=await setup({async request(path,options) {
      if(options?.method){posts++;return {};}
      if(++reads===2)await new Promise(resolve=>{release=resolve;});
      return {requests:[row()]};
    }},{getSession:()=>current});
    fire(fill(root),'submit');await tick();
    current=change(current);release();await tick();
    assert.equal(posts,0);
    assert.equal(root.querySelector('[data-renewal-record]'),null);
    assert.equal(handle.openRecord(id(1)),false);
    handle.dispose();
  }
});

test('same actor token refresh remains valid and double confirm sends only once', async () => {
  let current=structuredClone(session), posts=0, release;
  const {root,handle}=await setup({async request(path,options) {
    if(options?.method){posts++;await new Promise(resolve=>{release=resolve;});return {request:approved(row(),options.body)};}
    return {requests:[row()]};
  }},{getSession:()=>current});
  const form=fill(root);fire(form,'submit');await tick();
  current={...current,access_token:'rotated-synthetic-token'};
  root.querySelector('[data-renewal-confirm-ack]').checked=true;
  const button=root.querySelector('[data-renewal-confirm-action]');
  fire(button,'click');fire(button,'click');await tick();
  assert.equal(posts,1);release();await tick();
  assert.equal(handle.isWritePending(),false);
  handle.dispose();
});

test('an edit during confirmation preflight invalidates the actual immutable command', async () => {
  let reads=0, release,posts=0;
  const {root,handle}=await setup({async request(path,options) {
    if(options?.method){posts++;return {};}
    if(++reads===3)await new Promise(resolve=>{release=resolve;});
    return {requests:[row()]};
  }});
  const form=fill(root);fire(form,'submit');await tick();
  root.querySelector('[data-renewal-confirm-ack]').checked=true;
  fire(root.querySelector('[data-renewal-confirm-action]'),'click');await tick();
  form.querySelector('[name="approved_principal"]').value='10000.01';
  release();await tick();
  assert.equal(posts,0);assert.match(root.textContent,/changed/);
  handle.dispose();
});

test('checked verification drafts require explicit discard during refresh', async () => {
  let reads=0, asks=0;
  const previous=globalThis.confirm;
  globalThis.confirm=()=>{asks++;return false;};
  try {
    const {root,handle}=await setup({async request(){reads++;return {requests:[row()]};}});
    const form=root.querySelector('[data-renewal-terms]');
    form.querySelector('[name="government_id_verified"]').checked=true;
    assert.equal(await handle.refresh({status:'approved'}),false);
    assert.equal(asks,1);assert.equal(reads,1);
    assert.equal(root.querySelector('[data-renewal-terms]'),form);
    handle.dispose();
  } finally {globalThis.confirm=previous;}
});

test('denied preflight clears private rows and stale handlers cannot retry', async () => {
  let reads=0, posts=0;
  const {root,handle}=await setup({async request(path,options){
    if(options?.method){posts++;return {};}
    if(++reads>1)throw Object.assign(new Error('private detail'),{status:403});
    return {requests:[row()]};
  }});
  const form=fill(root);fire(form,'submit');await tick();
  assert.equal(root.querySelector('[data-renewal-record]'),null);
  assert.doesNotMatch(root.textContent,/Same Name|private detail/);
  fire(form,'submit');await tick();
  assert.equal(reads,2);assert.equal(posts,0);
  handle.dispose();
});

test('contradictory signed or duplicated terms results never become confirmed success', async () => {
  const {mod,handle}=await setup({async request(){return {requests:[]};}});
  const signer={party_role:'borrower',full_name:'Person',user_id:id(301),government_id_verified:false,selfie_verified:false};
  const command={action:'terms',request:row(),body:{decision:'approved',approved_principal:'10000.00',review_note:'Reviewed',override_reason:'',office_processing_required:false,signers:[signer]}};
  const result=approved(row(),command.body);
  assert.equal(mod.renewalResultMatches(command,{request:{...result,signers:[{...result.signers[0],signed:true}]}}),false);
  assert.equal(mod.renewalResultMatches(command,{request:{...result,signer_readiness_status:'ready'}}),false);
  handle.dispose();
});

test('saved write stays saved if the affected overview read callback fails', async () => {
  let posts=0;
  const {root,handle}=await setup({async request(path,options){
    if(options?.method){posts++;return {request:approved(row(),options.body)};}
    return {requests:[row()]};
  }},{onSaved:async()=>{throw new Error('read failure');}});
  await confirm(root,fill(root));
  assert.equal(posts,1);assert.equal(handle.isWritePending(),false);
  assert.match(root.textContent,/Terms saved.*Overview refresh failed/);
  handle.dispose();
});

test('an uncertain terms POST reconciles with exact saved state without a second POST', async () => {
  let saved=null,posts=0;
  const {root,handle}=await setup({async request(path,options){
    if(options?.method){posts++;saved=approved(row(),options.body);throw Object.assign(new Error('lost response'),{status:503});}
    return {requests:path.endsWith('status=approved')&&saved?[saved]:[row()]};
  }});
  await confirm(root,fill(root));assert.equal(handle.isWritePending(),true);
  fire(root.querySelector('[data-renewal-reconcile]'),'click');await tick();
  assert.equal(handle.isWritePending(),false);assert.equal(posts,1);
  assert.match(root.textContent,/Matching saved state verified/);
  handle.dispose();
});

test('offline confirmation cannot POST or claim a saved result', async () => {
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
  let posts=0;
  try {
    Object.defineProperty(globalThis,'navigator',{configurable:true,value:{onLine:false}});
    const {root,handle}=await setup({async request(path,options){if(options?.method)posts++;return {requests:[row()]};}});
    await confirm(root,fill(root));assert.equal(posts,0);assert.match(root.textContent,/Connect to the server/);
    handle.dispose();
  }finally{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else delete globalThis.navigator;}
});

test('private-photo denial clears current queue and its retained photo URL', async () => {
  const item=row(1,{status:'approved',approved_principal:'10000.00'});
  const {root,handle}=await setup({async request(path,options){
    if(options?.responseType==='blob')throw Object.assign(new Error('secret location'),{status:403});
    return {requests:path.endsWith('status=approved')?[item]:[]};
  }});
  await handle.refresh({status:'approved'});
  const button=root.querySelector('[data-renewal-photo]');fire(button,'click');await tick();
  assert.equal(root.querySelector('[data-renewal-record]'),null);
  assert.doesNotMatch(root.textContent,/Same Name|secret location/);
  handle.dispose();
});

test('a supported photo header with undecodable image bytes is not viewable evidence', async () => {
  const previous=globalThis.createImageBitmap;
  globalThis.createImageBitmap=async()=>{throw new Error('decode failed');};
  try {
    const item=row(1,{status:'approved',approved_principal:'10000.00'});
    const {root,handle}=await setup({async request(path,options){
      if(options?.responseType==='blob')return new Blob([new Uint8Array([137,80,78,71,13,10,26,10,1])],{type:'image/png'});
      return {requests:path.endsWith('status=approved')?[item]:[]};
    }});
    await handle.refresh({status:'approved'});fire(root.querySelector('[data-renewal-photo]'),'click');await tick();
    assert.equal(root.querySelector('img'),null);
    assert.match(root.textContent,/photo is unavailable/);
    handle.dispose();
  }finally{if(previous)globalThis.createImageBitmap=previous;else delete globalThis.createImageBitmap;}
});
