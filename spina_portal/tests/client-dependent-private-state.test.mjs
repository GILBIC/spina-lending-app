import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountPaymentProofs} from '../assets/payment-proofs.js';
import {mountClientDocuments} from '../assets/client-documents.js';

const id='10000000-0000-4000-8000-000000000001';
const capability={upload_available:true,max_bytes:10485760};
for(const status of [401,403])test(`proof read ${status} clears private evidence controls and makes stale submit/retry inert`,async t=>{
  const root=new Element();let denied=false,handle;const calls=[];
  const dispose=mountPaymentProofs({root,loans:[{loan_id:id}],registerHandle:value=>handle=value,api:{async request(path,options={}){calls.push({path,options});if(denied)throw Object.assign(Error('Synthetic denied evidence'),{status});return {proofs:[],capability};}}});t.after(dispose);await setImmediate();
  const form=root.querySelector('[data-proof-upload]'),retry=root.querySelector('[data-proof-refresh]');form.querySelector('[name="proofFile"]').files=[new Blob(['synthetic'],{type:'image/png'})];form.querySelector('[name="loanId"]').value=id;form.querySelector('[name="note"]').value='Private synthetic note';
  denied=true;await handle.refreshReadOnly();assert.equal(root.querySelector('form'),null);assert.equal(root.querySelector('[data-proof-refresh]'),null);assert.doesNotMatch(root.textContent,/Private synthetic note/);
  fire(form,'submit');fire(retry,'click');await handle.refreshReadOnly();await setImmediate();assert.equal(calls.length,2);assert.equal(calls.filter(call=>call.options.method==='POST').length,0);
});

for(const status of [401,403])test(`document ${status} removes private links and stale controls cannot save or rerequest`,async t=>{
  const root=new Element(),calls=[],downloads=[];
  const dispose=mountClientDocuments({root,loans:[{loan_id:id,loan_number:'Private synthetic loan'}],payments:[{transaction_id:id,receipt_number:'Private synthetic receipt'}],saveFile:(...args)=>downloads.push(args),api:{async request(path){calls.push(path);throw Object.assign(Error('Synthetic denied document'),{status});}}});t.after(dispose);
  const statement=root.querySelector('[data-statement-copy]'),payment=root.querySelector('[data-payment-copy]'),original=root.querySelector('[data-load-documents]');fire(statement,'click');await setImmediate();assert.equal(root.querySelector('button'),null);assert.doesNotMatch(root.textContent,/Private synthetic loan|Private synthetic receipt/);
  fire(statement,'click');fire(payment,'click');fire(original,'click');await setImmediate();assert.equal(calls.length,1);assert.deepEqual(downloads,[]);
});

test('missing or malformed proof capability leaves loaded history readable without enabling upload',async t=>{
  for(const value of [undefined,null,{}, {upload_available:'true',max_bytes:10485760},{upload_available:true,max_bytes:'10485760'}]){
    const root=new Element(),dispose=mountPaymentProofs({root,loans:[{loan_id:id}],api:{async request(){return {proofs:[{proof_id:id,loan_number:'Existing evidence',status:'submitted'}],capability:value};}}});t.after(dispose);await setImmediate();
    assert.equal(root.querySelector('[data-proof-upload]'),null);assert.ok(root.querySelector('[data-proof-detail]'));assert.ok(root.querySelector('[data-proof-refresh]'));assert.match(root.textContent,/unavailable/i);dispose();
  }
});

test('read-only recovery cannot reset or replay an uncertain proof attempt',async t=>{
  const root=new Element(),calls=[];let handle;
  const dispose=mountPaymentProofs({root,loans:[{loan_id:id}],registerHandle:value=>handle=value,api:{async request(path,options={}){calls.push({path,options});if(options.method==='POST')throw Object.assign(Error('Synthetic response lost'),{code:'network_uncertain'});return {proofs:[],capability};}}});t.after(dispose);await setImmediate();
  const form=root.querySelector('[data-proof-upload]'),input=form.querySelector('[name="proofFile"]'),file=new Blob(['original exact bytes'],{type:'image/png'});input.files=[file];form.querySelector('[name="loanId"]').value=id;form.querySelector('[name="note"]').value='Original reference';fire(form,'submit');await setImmediate();assert.equal(handle.isUncertain(),true);
  await handle.refreshReadOnly();await handle.openRecord(id);assert.equal(calls.length,2);assert.strictEqual(root.querySelector('[name="proofFile"]'),input);assert.strictEqual(input.files[0],file);
  fire(form,'submit');await setImmediate();assert.equal(calls.length,3);assert.equal(calls[1].path,calls[2].path);assert.strictEqual(calls[1].options.rawBody,file);assert.strictEqual(calls[2].options.rawBody,file);assert.deepEqual(calls[1].options.headers,calls[2].options.headers);
});

for(const replacement of [{upload_available:false},{upload_available:'yes',max_bytes:10485760},{upload_available:true,max_bytes:'10485760'},null])test(`a refreshed invalid or disabled proof capability blocks the retained draft: ${JSON.stringify(replacement)}`,async t=>{
  const root=new Element(),calls=[];let handle,currentCapability=capability;
  const dispose=mountPaymentProofs({root,loans:[{loan_id:id}],registerHandle:value=>handle=value,api:{async request(path,options={}){calls.push({path,options});if(options.method==='POST')return {};return {proofs:[],capability:currentCapability};}}});t.after(dispose);await setImmediate();
  const form=root.querySelector('[data-proof-upload]'),input=form.querySelector('[name="proofFile"]'),file=new Blob(['retained exact bytes'],{type:'image/png'});
  Object.defineProperty(form,'parentNode',{get:()=>form.parentElement});input.files=[file];form.querySelector('[name="loanId"]').value=id;form.querySelector('[name="note"]').value='Retain this evidence draft';
  currentCapability=replacement;await handle.refreshReadOnly();assert.strictEqual(root.querySelector('[data-proof-upload]'),form);assert.strictEqual(input.files[0],file);assert.equal(form.querySelector('button[type="submit"]').disabled,true);
  form.querySelector('button[type="submit"]').disabled=false;fire(form,'submit');await setImmediate();assert.equal(calls.filter(call=>call.options.method==='POST').length,0);assert.match(root.textContent,/unavailable/i);
  currentCapability=capability;await handle.refreshReadOnly();assert.strictEqual(root.querySelector('[name="proofFile"]'),input);assert.strictEqual(input.files[0],file);assert.equal(form.querySelector('[name="note"]').value,'Retain this evidence draft');assert.equal(form.querySelector('button[type="submit"]').disabled,false);
});

test('an authorized existing correction uses its exact proof/version while failed loan selection still blocks new evidence',async t=>{
  const root=new Element(),calls=[];let handle;
  const version={version_number:2,media_type:'image/png',uploaded_at:'2026-10-02T01:00:00Z'},proof={proof_id:id,loan_id:id,status:'correction_required',can_reupload:true,current_version:version};
  const detail={proof,history:[{version,reviews:[]}]};
  const dispose=mountPaymentProofs({root,loansState:{status:'error'},registerHandle:value=>handle=value,api:{async request(path,options={}){calls.push({path,options});if(options.method==='POST'){const next={...version,version_number:3};return {proof:{...proof,current_version:next,can_reupload:false},history:[{version:next,reviews:[]}]};}return path.endsWith(id)?detail:{proofs:[proof],capability};}}});t.after(dispose);await setImmediate();
  assert.equal(root.querySelector('[data-proof-upload]'),null);await handle.openRecord(id);const form=root.querySelector('[data-proof-upload]');assert.ok(form,'verified existing correction must not depend on new-loan selection');assert.equal(form.querySelector('[name="loanId"]'),null);
  const file=new Blob(['corrected bytes'],{type:'image/png'});form.querySelector('[name="proofFile"]').files=[file];fire(form,'submit');await setImmediate();const posts=calls.filter(call=>call.options.method==='POST');assert.equal(posts.length,1);assert.ok(posts[0].path.startsWith(`/api/v1/client/payment-proofs/${id}/versions?`));assert.equal(new URL(posts[0].path,'https://spina.test').searchParams.get('expected_version'),'2');assert.strictEqual(posts[0].options.rawBody,file);assert.equal(root.querySelector('[data-proof-upload]'),null);
});

test('proof read recovery uses current authorized loan state without requiring a workspace remount',async t=>{
  const root=new Element();let handle,loans={status:'error'};
  const dispose=mountPaymentProofs({root,loansState:loans,getLoansState:()=>loans,registerHandle:value=>handle=value,api:{async request(){return {proofs:[],capability};}}});t.after(dispose);await setImmediate();assert.equal(root.querySelector('[data-proof-upload]'),null);
  loans={status:'ready',data:{loans:[{loan_id:id,loan_number:'Recovered own loan'}]}};await handle.refreshReadOnly();const form=root.querySelector('[data-proof-upload]');assert.ok(form);assert.match(form.textContent,/Recovered own loan/);assert.equal(form.querySelector('option').getAttribute('value'),id);
});
