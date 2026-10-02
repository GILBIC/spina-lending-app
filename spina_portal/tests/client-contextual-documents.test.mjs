import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';
import {downloadClientRecordCopy} from '../assets/client-documents.js';

const id='10000000-0000-4000-8000-000000000001';
const otherId='10000000-0000-4000-8000-000000000002';
const flush=async()=>{await setImmediate();await setImmediate();};
const deferred=()=>{let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};};
const pdf=()=>new Blob(['synthetic private PDF'],{type:'application/pdf'});
const failure=status=>Object.assign(Error(`Synthetic copy failure ${status}`),{status});
const variants=[
 {kind:'payment',section:'client-payments',copy:'[data-payment-record-copy]',status:'[data-payment-download-status]',key:'payments',path:`/api/v1/client/payments/${id}/document`},
 {kind:'statement',section:'client-statement',copy:'[data-client-statement-copy]',status:'[data-client-statement-download-status]',key:'statement',path:'/api/v1/client/statement/document'},
];
async function mount(t,variant){
 const prior={document:globalThis.document,setTimeout:globalThis.setTimeout,create:URL.createObjectURL,revoke:URL.revokeObjectURL};
 const saved=[],created=[],revoked=[],timers=[];
 globalThis.document={createElement:()=>({click(){saved.push({href:this.href,name:this.download});}})};
 globalThis.setTimeout=fn=>{timers.push(fn);return {unref(){}};};
 URL.createObjectURL=blob=>{created.push(blob);return `blob:synthetic-${created.length}`;};URL.revokeObjectURL=url=>revoked.push(url);
 t.after(()=>{globalThis.document=prior.document;globalThis.setTimeout=prior.setTimeout;URL.createObjectURL=prior.create;URL.revokeObjectURL=prior.revoke;});
 const root=new Element(),controller=new AbortController(),calls=[],copies=[];
 const query=root.querySelectorAll.bind(root);root.querySelectorAll=selector=>{const pair=selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);return pair?query(pair[1]).filter(n=>n.getAttribute(pair[2].slice(1,-1))!==null):query(selector);};
 const session={user:{id:'synthetic-owner',role:'client'},device_id:'synthetic-device',access_token:'original-token'};
 const values={payments:{payments:[{transaction_id:id,receipt_number:'Same receipt',amount:'12.34'},{transaction_id:otherId,receipt_number:'Same receipt',amount:'12.34'}]},statement:{client:{client_name:'Synthetic'},loans:[],payments:[]}};
 let handle;
 const context={root,signal:controller.signal,getSession:()=>session,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});assert.notEqual(options.method,'POST');
  if(path.endsWith('/document')){const pending=deferred();copies.push({path,options,...pending});return pending.promise;}
  if(path==='/api/v1/account')return {profile:{full_name:'Synthetic'}};
  if(path==='/api/v1/activity-notifications')return [];
  if(path==='/api/v1/client/loans')return {loans:[]};
  if(path.startsWith('/api/v1/client/payment-proofs'))return {proofs:[],capability:{upload_available:true,max_bytes:10485760}};
  if(path==='/api/v1/client/payments')return values.payments;
  if(path==='/api/v1/client/statement')return values.statement;
  return {requests:[]};
 }}};
 await mountClientWorkspace(context);await handle.activate('client-payment-proofs');await handle.activate(variant.section);await flush();
 t.after(()=>controller.abort());
 const support=root.querySelector('#client-support-form').querySelector('[name="message"]'),file=root.querySelector('[name="proofFile"]');support.value='Private retained draft';file.value='synthetic.png';
 const open=()=>{if(variant.kind==='payment')fire(root.querySelector(`[data-payment-details="${id}"]`),'click');return root.querySelector(variant.copy);};
 return {root,controller,context,session,handle,calls,copies,saved,created,revoked,timers,values,support,file,open,refresh:()=>context.clientLoad(variant.key,{refresh:true})};
}

for(const variant of variants){
 test(`${variant.kind} copy is explicit, exact, private and deduplicated while pending`,async t=>{
  const h=await mount(t,variant),button=h.open();assert.equal(h.copies.length,0);
  fire(button,'click');button.disabled=false;fire(button,'click');await flush();
  assert.equal(h.copies.length,1,'forced repeated activation must not duplicate a pending copy');
  assert.equal(h.copies[0].path,variant.path);assert.equal(h.copies[0].options.responseType,'blob');
  h.copies[0].resolve(pdf());await flush();assert.equal(h.saved.length,1);assert.equal(h.saved[0].href,'blob:synthetic-1');
  assert.match(h.saved[0].name,variant.kind==='payment'?new RegExp(id):/statement-of-account/);
  h.timers.forEach(fn=>fn());assert.deepEqual(h.revoked,['blob:synthetic-1']);
  assert.equal(h.support.value,'Private retained draft');assert.equal(h.file.value,'synthetic.png');
 });
 for(const outcome of ['success','error'])test(`${variant.kind} refresh invalidates its prior copy and cannot affect replacement status (${outcome})`,async t=>{
  const h=await mount(t,variant),button=h.open();fire(button,'click');await flush();
  await h.refresh();const replacement=h.open(),status=h.root.querySelector(variant.status);status.textContent='New view status';
  if(outcome==='success')h.copies[0].resolve(pdf());else h.copies[0].reject(failure(503));await flush();
  assert.equal(h.copies[0].options.signal.aborted,true,'replacing a read view must cancel its pending copy');
  assert.equal(h.saved.length,0);assert.equal(status.textContent,'New view status');
  button.disabled=false;fire(button,'click');await flush();assert.equal(h.copies.length,1,'detached prior controls must be inert');
  fire(replacement,'click');await flush();assert.equal(h.copies.length,2);h.copies[1].resolve(pdf());await flush();assert.equal(h.saved.length,1);
 });
 for(const status of [401,403])for(const replaced of [false,true])test(`${variant.kind} ${status} clears private current-mount inputs even when replaced=${replaced}`,async t=>{
  const h=await mount(t,variant),button=h.open();fire(button,'click');await flush();
  if(replaced){await h.refresh();button.isConnected=false;}
  h.copies[0].reject(failure(status));await flush();
  assert.equal(h.root.innerHTML,'');assert.equal(h.support.value,'');assert.equal(h.file.value,'');assert.equal(h.file.disabled,true);
  button.disabled=false;fire(button,'click');await flush();assert.equal(h.copies.length,1);
 });
 for(const loss of ['abort','owner','device'])test(`${variant.kind} late bytes after ${loss} never save`,async t=>{
  const h=await mount(t,variant);fire(h.open(),'click');await flush();
  if(loss==='abort')h.controller.abort();else if(loss==='owner')h.session.user.id='replacement-owner';else h.session.device_id='replacement-device';
  h.copies[0].resolve(pdf());await flush();assert.equal(h.saved.length,0);assert.equal(h.root.innerHTML,'');assert.equal(h.file.value,'');
 });
 test(`${variant.kind} old-mount denial cannot clear a replacement mount`,async t=>{
  const h=await mount(t,variant);fire(h.open(),'click');await flush();h.controller.abort();h.root.innerHTML='<input name="replacement" />';
  const replacement=h.root.querySelector('input');replacement.value='Replacement private draft';h.copies[0].reject(failure(403));await flush();
  assert.equal(h.root.querySelector('input'),replacement);assert.equal(replacement.value,'Replacement private draft');assert.equal(replacement.disabled,false);
 });
 test(`${variant.kind} token rotation retains authority and temporary errors permit an explicit retry`,async t=>{
  const h=await mount(t,variant),button=h.open();fire(button,'click');await flush();h.copies[0].reject(failure(503));await flush();
  assert.match(h.root.querySelector(variant.status).textContent,/503/);assert.equal(button.disabled,false);assert.equal(h.file.value,'synthetic.png');
  h.session.access_token='rotated-token';fire(button,'click');await flush();h.copies[1].resolve(pdf());await flush();assert.equal(h.saved.length,1);
 });
}

test('payment Close aborts pending bytes and stale close/copy handlers cannot affect a reopened disclosure',async t=>{
 const h=await mount(t,variants[0]),button=h.open(),close=h.root.querySelector('[data-payment-detail-close]');
 fire(button,'click');await flush();fire(close,'click');const replacement=h.open(),status=h.root.querySelector(variants[0].status);status.textContent='New disclosure';
 h.copies[0].reject(failure(503));await flush();assert.equal(status.textContent,'New disclosure');assert.equal(h.copies[0].options.signal.aborted,true);
 fire(close,'click');assert.equal(h.root.querySelector(variants[0].copy),replacement);
 fire(button,'click');await flush();assert.equal(h.copies.length,1);
 fire(replacement,'click');await flush();h.copies[1].resolve(pdf());await flush();assert.equal(h.saved.length,1);
});

test('payment Close without reopening safely ignores late errors',async t=>{
 const h=await mount(t,variants[0]);fire(h.open(),'click');await flush();fire(h.root.querySelector('[data-payment-detail-close]'),'click');
 h.copies[0].reject(failure(503));await flush();assert.equal(h.copies[0].options.signal.aborted,true);assert.equal(h.root.querySelector(variants[0].status),null);
});

test('a same-looking second payment uses its own immutable ID and stale membership cannot download',async t=>{
 const h=await mount(t,variants[0]);fire(h.root.querySelector(`[data-payment-details="${otherId}"]`),'click');
 const copy=h.root.querySelector(`[data-payment-record-copy="${otherId}"]`);fire(copy,'click');await flush();assert.equal(h.copies[0].path,`/api/v1/client/payments/${otherId}/document`);h.copies[0].resolve(pdf());await flush();
 h.context.clientReads.state('payments').data.payments=[];fire(copy,'click');await flush();assert.equal(h.copies.length,1);
});

for(const [name,result]of [['empty',new Blob([],{type:'application/pdf'})],['wrong MIME',new Blob(['HTML'],{type:'text/html'})],['non-Blob',{url:'https://untrusted.invalid/private.pdf'}]])test(`record helper rejects ${name} instead of saving or following a URL`,async()=>{
 const saved=[];await assert.rejects(downloadClientRecordCopy({api:{request:async()=>result},kind:'payment',transactionId:id,saveFile:(...args)=>saved.push(args)}),/valid document file/);assert.deepEqual(saved,[]);
});
test('record helper rejects invalid kind/ID before any request and aborted valid bytes never save',async()=>{
 const saved=[],calls=[];const api={request:async(...args)=>{calls.push(args);return pdf();}};
 for(const options of [{kind:'packet'},{kind:'payment',transactionId:'not-a-uuid'},{kind:'payment'}])await assert.rejects(downloadClientRecordCopy({api,...options}),/valid authorized record/);
 assert.equal(calls.length,0);const controller=new AbortController(),pending=deferred();
 const work=downloadClientRecordCopy({api:{request:()=>pending.promise},kind:'statement',signal:controller.signal,saveFile:(...args)=>saved.push(args)});controller.abort();pending.resolve(pdf());await work;assert.deepEqual(saved,[]);
});


test('Statement copy remains honestly whole-account and distinct from the original released documents',async t=>{
 const h=await mount(t,variants[1]);const button=h.open();assert.equal(button.textContent,'Download statement copy (PDF)');
 assert.doesNotMatch(h.root.querySelector('[data-client-region="statement"]').textContent,/filtered|original released/i);
 await h.handle.activate('client-documents');await flush();assert.match(h.root.querySelector('[data-client-documents]').textContent,/original released loan packet/);
 assert.match(h.root.querySelector('[data-client-documents]').textContent,/current statement and payment record copies/);assert.equal(h.copies.length,0);
});
