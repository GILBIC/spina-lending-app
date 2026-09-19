import assert from 'node:assert/strict';
import test from 'node:test';
import { Element, fire } from './helpers/dom.mjs';

const module = await import('../assets/payment-proofs.js').catch(() => ({}));
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const id = '10000000-0000-4000-8000-000000000001';
const version = {version_number: 2, media_type:'image/png', note:'old', uploaded_at:'2026-09-19T01:00:00Z'};
const proof = {proof_id:id, loan_id:id, loan_number:'LOAN-1', status:'correction_required', current_version:version,
  can_reupload:true, latest_review:{review_id:id, decision:'correction_required', reason:'Wrong image'}};
const detail = {proof, history:[{version, reviews:[proof.latest_review]}]};
const capability = {upload_available:true, max_bytes:10485760, allowed_media_types:['image/png'], posts_payment:false};

test('An uncertain proof upload retries the identical request and bytes without posting a payment', async () => {
  assert.equal(typeof module.mountPaymentProofs, 'function');
  const root = new Element(); const posts = [];
  module.mountPaymentProofs({root, loans:[{loan_id:id, loan_number:'LOAN-1'}], api:{request:async (path, options={}) => {
    if (options.method === 'POST') { posts.push({path,options}); if(posts.length===1) throw Object.assign(new Error('Connection interrupted'),{code:'network_uncertain'}); return detail; }
    return {proofs:[], capability, has_more:false};
  }}}); await tick();
  const file = new Blob(['png'],{type:'image/png'});
  root.querySelector('[name="proofFile"]').files=[file];
  root.querySelector('[name="loanId"]').value=id;
  root.querySelector('[name="note"]').value='Paid by José';
  fire(root.querySelector('[data-proof-upload]'),'submit'); await tick();
  assert.match(root.textContent,/Retry the same submission/);
  assert.equal(root.querySelector('[name="proofFile"]').disabled,true);
  fire(root.querySelector('[data-proof-upload]'),'submit'); await tick();
  assert.equal(posts.length,2); assert.equal(posts[0].path,posts[1].path);
  assert.equal(posts[0].options.rawBody,file); assert.equal(posts[1].options.rawBody,file);
  assert.equal(new URL(posts[0].path,'https://spina.test').searchParams.has('note'),false);
  assert.equal(Buffer.from(posts[0].options.headers['X-Proof-Note'],'base64').toString('utf8'),'Paid by José');
  assert.match(posts[0].path,/^\/api\/v1\/client\/payment-proofs\?/);
  assert.doesNotMatch(posts[0].path,/collections|payments\/post/);
  assert.match(root.textContent,/does not change your balance/);
});

test('Correction preserves review history and submits the server version', async () => {
  assert.equal(typeof module.mountPaymentProofs,'function');
  const root=new Element(); let posted;
  module.mountPaymentProofs({root,loans:[{loan_id:id,loan_number:'LOAN-1'}],api:{request:async(path,options={})=>{
    if(options.method==='POST'){posted={path,options};return detail;}
    return path.endsWith(id)?detail:{proofs:[proof],capability,has_more:false};
  }}});await tick();fire(root.querySelector('[data-proof-detail]'),'click');await tick();
  assert.match(root.textContent,/Wrong image/);assert.match(root.textContent,/Version 2/);
  root.querySelector('[name="proofFile"]').files=[new Blob(['new'],{type:'image/png'})];
  fire(root.querySelector('[data-proof-upload]'),'submit');await tick();
  assert.match(posted.path,new RegExp(`/payment-proofs/${id}/versions\\?`));
  assert.equal(new URL(posted.path,'https://spina.test').searchParams.get('expected_version'),'2');
});

test('Management review sends version and latest review guard; reviewed means evidence only', async () => {
  assert.equal(typeof module.mountPaymentProofs,'function');
  const root=new Element();let posted;
  module.mountPaymentProofs({root,mode:'management',api:{request:async(path,options={})=>{
    if(options.method==='POST'){posted={path,options};return detail;}
    return path.endsWith(id)?detail:{proofs:[proof],capability,has_more:false};
  }}});await tick();fire(root.querySelector('[data-proof-detail]'),'click');await tick();
  root.querySelector('[name="decision"]').value='reviewed';
  fire(root.querySelector('[data-proof-review]'),'submit');await tick();
  assert.equal(posted.path,`/api/v1/management/payment-proofs/${id}/reviews`);
  assert.equal(posted.options.body.expected_version,2);assert.equal(posted.options.body.expected_review_id,id);
  assert.equal(posted.options.body.reason,'');
  assert.match(root.textContent,/does not confirm settlement/);
});

test('Unavailable storage and an aborted request fail closed', async () => {
  assert.equal(typeof module.mountPaymentProofs,'function');
  const root=new Element();let resolve;const controller=new AbortController();
  module.mountPaymentProofs({root,signal:controller.signal,api:{request:()=>new Promise((done)=>{resolve=done;})}});
  controller.abort();resolve({proofs:[proof],capability});await tick();assert.equal(root.innerHTML,'');
  module.mountPaymentProofs({root,loans:[{loan_id:id}],api:{request:async()=>({proofs:[],capability:{upload_available:false,message:'Unavailable'}})}});
  await tick();assert.equal(root.querySelector('[data-proof-upload]'),null);assert.match(root.textContent,/Unavailable/);
});

test('Unreadable successful upload response preserves retry identity and never claims saved', async () => {
  const root=new Element();const posts=[];
  module.mountPaymentProofs({root,loans:[{loan_id:id,loan_number:'LOAN-1'}],api:{request:async(path,options={})=>{
    if(options.method==='POST'){posts.push({path,options});return posts.length===1?null:detail;}
    return {proofs:[],capability,has_more:false};
  }}});await tick();
  root.querySelector('[name="loanId"]').value=id;
  const file=new Blob(['png'],{type:'image/png'});root.querySelector('[name="proofFile"]').files=[file];
  fire(root.querySelector('[data-proof-upload]'),'submit');await tick();
  assert.match(root.textContent,/Retry the same submission/);assert.doesNotMatch(root.textContent,/Evidence saved for review/);
  fire(root.querySelector('[data-proof-upload]'),'submit');await tick();
  assert.equal(posts[0].path,posts[1].path);assert.equal(posts[1].options.rawBody,file);
  assert.match(root.textContent,/Evidence saved for review/);
});

test('Evidence download never saves an HTML error body as a private image', async () => {
  const root=new Element();const saved=[];
  module.mountPaymentProofs({root,saveFile:(...args)=>saved.push(args),api:{request:async(path)=>{
    if(path.endsWith('/content'))return new Blob(['<html>Error</html>'],{type:'text/html'});
    return path.endsWith(id)?detail:{proofs:[proof],capability,has_more:false};
  }}});await tick();fire(root.querySelector('[data-proof-detail]'),'click');await tick();
  fire(root.querySelector('[data-proof-content]'),'click');await tick();assert.equal(saved.length,0);assert.match(root.textContent,/valid.*file/);
});
