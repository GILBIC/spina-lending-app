import test from 'node:test';import assert from 'node:assert/strict';import {Element,fire} from './helpers/dom.mjs';import {mountClientWorkspace} from '../assets/roles/client.js';
const tick=()=>new Promise(r=>setTimeout(r,0));
test('pending Updates and Statement do not block the shell; Statement revisits deduplicate actual reads',async()=>{
 const root=new Element();let handle;const calls=[];const controller=new AbortController();
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{request(path){calls.push(path);if(path==='/api/v1/account')return Promise.resolve({});if(path==='/api/v1/client/loans')return Promise.resolve({loans:[]});return new Promise(()=>{});}}};
 void mountClientWorkspace(context);await tick();assert.ok(root.querySelector('#client-support-form'));assert.equal(typeof handle?.activate,'function');assert.equal(calls.includes('/api/v1/client/statement'),false);handle.activate('client-statement');handle.activate('client-statement');assert.equal(calls.filter(x=>x==='/api/v1/client/statement').length,1);controller.abort();assert.equal(root.innerHTML,'');
});
test('header refresh preserves mounted unrelated forms',async()=>{
 const root=new Element();let handle;const context={root,setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{request:async path=>path.includes('loans')?{loans:[]}:path.includes('notifications')?[]:{}}};await mountClientWorkspace(context);await tick();const form=root.querySelector('#client-support-form');form.querySelector('[name="message"]').value='keep draft';await handle.refreshVisible();assert.equal(root.querySelector('#client-support-form'),form);assert.equal(form.querySelector('[name="message"]').value,'keep draft');handle.dispose();
});

const firstLoan='10000000-0000-4000-8000-000000000001',secondLoan='10000000-0000-4000-8000-000000000002';
const clientId='20000000-0000-4000-8000-000000000001';
const flush=async()=>{await new Promise(resolve=>setImmediate(resolve));await new Promise(resolve=>setImmediate(resolve));};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
const loans={client:{client_id:clientId},loans:[firstLoan,secondLoan].map((loan_id,index)=>({loan_id,loan_number:`Synthetic loan ${index+1}`,loan_type_name:'7x7',status:'active',daily_amount:'100.00'}))};
const schedule=id=>({loan_id:id,read_only:true,penalty_status:'penalty_outstanding',exact_payoff_total:id===firstLoan?'111.00':'222.00',assessed_penalty_balance:'5.00',projected_penalty:'0.00',rows:[{payment_date:'2050-01-01',amount:'100.00',status:'Scheduled',details:{remaining_amount:'40.00',note:id===firstLoan?'First schedule ready':'Second schedule ready'}}]});
const gcash={provider:'synthetic',mode:'sandbox',payment_available:true,message:'Synthetic payment configuration'};
const proof={proofs:[],capability:{upload_available:true,max_bytes:10485760}};

async function independent(t,overrides=new Map()){
 const root=new Element(),controller=new AbortController(),calls=[];let handle;
 const session={user:{id:'synthetic-owner',role:'client',client_id:clientId},device:{id:'synthetic-device'},permissions:['synthetic-existing-grant'],access_token:'first-token'};
 const context={root,signal:controller.signal,session,getSession:()=>session,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});assert.notEqual(options.method,'POST','loading acceptance must not write');
  const key=path.split('?')[0];if(overrides.has(key)){const value=overrides.get(key);if(value instanceof Error)throw value;return typeof value==='function'?value():value;}
  if(key==='/api/v1/account')return {profile:{full_name:'Independent synthetic account'}};
  if(key==='/api/v1/client/loans')return loans;
  const loan=key.match(/\/loans\/([^/]+)\/schedule$/)?.[1];if(loan)return schedule(loan);
  if(key==='/api/v1/activity-notifications')return [];
  if(key==='/api/v1/client/gcash/config')return gcash;
  if(key==='/api/v1/client/payment-proofs')return proof;
  if(key==='/api/v1/client/payments')return {payments:[]};
  if(key==='/api/v1/client/renewals')return {loans:[],requests:[]};
  if(key==='/api/v1/client/statement')return {client:{client_id:clientId,client_name:'Ready statement'},loans:[],payments:[]};
  return {requests:[]};
 }}};
 await mountClientWorkspace(context);t.after(()=>controller.abort());await flush();
 return {root,controller,calls,context,session,handle,overrides,count:path=>calls.filter(call=>call.path.split('?')[0]===path).length};
}

test('one exact loan stays usable while another schedule and independent secondary reads wait',async t=>{
 const waiting=Object.fromEntries(['schedule','updates','statement','proof','gcash'].map(key=>[key,deferred()]));
 const h=await independent(t,new Map([
  [`/api/v1/client/loans/${secondLoan}/schedule`,waiting.schedule.promise],['/api/v1/activity-notifications',waiting.updates.promise],
  ['/api/v1/client/statement',waiting.statement.promise],['/api/v1/client/payment-proofs',waiting.proof.promise],['/api/v1/client/gcash/config',waiting.gcash.promise],
 ]));
 assert.match(h.root.querySelector('[data-client-region="account"]').textContent,/Independent synthetic account/);
 assert.ok(h.root.querySelector('#client-support-form'));
 for(const path of ['/api/v1/client/statement','/api/v1/client/payment-proofs','/api/v1/client/gcash/config','/api/v1/client/payments','/api/v1/client/renewals','/api/v1/client/renewal-workflow','/api/v1/client/support'])assert.equal(h.count(path),0,`${path} must wait for activation`);
 const first=h.root.querySelector(`[data-client-schedule-loan="${firstLoan}"]`),second=h.root.querySelector(`[data-client-schedule-loan="${secondLoan}"]`);
 fire(first,'click');fire(second,'click');await flush();
 const firstPanel=first.closest('.loan-card').querySelector('[data-client-schedule-panel]'),secondPanel=second.closest('.loan-card').querySelector('[data-client-schedule-panel]');
 assert.match(firstPanel.textContent,/First schedule ready/);assert.match(secondPanel.textContent,/Loading authoritative schedule/);
 assert.equal(h.count(`/api/v1/client/loans/${firstLoan}/schedule`),1);assert.equal(h.count(`/api/v1/client/loans/${secondLoan}/schedule`),1);
 const support=h.root.querySelector('#client-support-form');support.querySelector('[name="message"]').value='Keep independent draft';
 for(let visit=0;visit<3;visit++)for(const id of ['client-statement','client-payment-proofs','client-payment-instructions'])await h.handle.activate(id);
 for(const path of ['/api/v1/client/statement','/api/v1/client/payment-proofs','/api/v1/client/gcash/config'])assert.equal(h.count(path),1);
 assert.match(firstPanel.textContent,/First schedule ready/);assert.equal(h.root.querySelector('#client-support-form'),support);
 waiting.statement.resolve({client:{client_id:clientId,client_name:'Ready statement'},loans:[],payments:[]});waiting.proof.resolve(proof);waiting.gcash.resolve(gcash);await flush();
 const proofForm=h.root.querySelector('[data-proof-upload]'),checkout=h.root.querySelector('#client-gcash-form');assert.ok(proofForm);assert.ok(checkout);
 proofForm.querySelector('[name="note"]').value='Keep proof editor';checkout.querySelector('[data-gcash-amount]').value='123.45';
 let proofListeners=0,checkoutListeners=0;const proofListen=proofForm.addEventListener.bind(proofForm),checkoutListen=checkout.addEventListener.bind(checkout);
 proofForm.addEventListener=(...args)=>{proofListeners++;return proofListen(...args);};checkout.addEventListener=(...args)=>{checkoutListeners++;return checkoutListen(...args);};
 for(let visit=0;visit<3;visit++)for(const id of ['client-statement','client-payment-proofs','client-payment-instructions'])await h.handle.activate(id);
 assert.equal(h.root.querySelector('[data-proof-upload]'),proofForm);assert.equal(h.root.querySelector('#client-gcash-form'),checkout);
 assert.equal(proofForm.querySelector('[name="note"]').value,'Keep proof editor');assert.equal(checkout.querySelector('[data-gcash-amount]').value,'123.45');
 assert.equal(proofListeners,0);assert.equal(checkoutListeners,0);
 for(const path of ['/api/v1/client/statement','/api/v1/client/payment-proofs','/api/v1/client/gcash/config'])assert.equal(h.count(path),1);
 assert.equal(h.context.clientReads.state('schedule:'+secondLoan).status,'loading');assert.equal(h.context.clientReads.state('notifications').status,'loading');
 waiting.schedule.resolve(schedule(secondLoan));waiting.updates.resolve([]);await flush();
 assert.match(secondPanel.textContent,/Second schedule ready/);assert.equal(support.querySelector('[name="message"]').value,'Keep independent draft');
});

test('a failed secondary read retries locally without reloading independent records or draft nodes',async t=>{
 const h=await independent(t,new Map([['/api/v1/client/statement',Object.assign(Error('Synthetic statement failure'),{status:503})]]));
 await h.handle.activate('client-statement');await flush();
 const region=h.root.querySelector('[data-client-region="statement"]'),form=h.root.querySelector('#client-support-form');form.querySelector('[name="message"]').value='Keep unrelated question';
 assert.match(region.textContent,/unavailable/);const count=h.calls.length;
 h.overrides.set('/api/v1/client/statement',{client:{client_id:clientId,client_name:'Recovered statement'},loans:[],payments:[]});
 fire(region.querySelector('[data-client-retry]'),'click');await flush();
 assert.equal(h.calls.length,count+1);assert.match(region.textContent,/Recovered statement/);
 assert.equal(h.root.querySelector('#client-support-form'),form);assert.equal(form.querySelector('[name="message"]').value,'Keep unrelated question');
});

const authorityChanges=[
 ['user',session=>session.user.id='other-owner'],['role',session=>session.user.role='employee'],
 ['device',session=>session.device.id='other-device'],['permissions',session=>session.permissions=[]],
 ['linked-client',session=>session.user.client_id='other-client'],
];
for(const [name,change]of authorityChanges)test(`${name} scope change rejects a late protected read and clears old drafts`,async t=>{
 const pending=deferred(),h=await independent(t,new Map([['/api/v1/client/statement',pending.promise]]));
 const form=h.root.querySelector('#client-support-form'),message=form.querySelector('[name="message"]');message.value='Old scope private draft';
 await h.handle.activate('client-statement');const calls=h.calls.length;change(h.session);
 pending.resolve({client:{client_id:clientId,client_name:'Stale protected statement'},loans:[],payments:[]});await flush();
 assert.equal(h.root.innerHTML,'');assert.equal(message.value,'');assert.equal(message.disabled,true);
 await h.handle.activate('client-statement');await h.handle.refreshVisible();assert.equal(h.calls.length,calls);
});

test('same-owner token rotation accepts the pending read and retains the current private editors',async t=>{
 const pending=deferred(),h=await independent(t,new Map([['/api/v1/client/statement',pending.promise]]));
 const form=h.root.querySelector('#client-support-form'),message=form.querySelector('[name="message"]');message.value='Same owner private draft';
 await h.handle.activate('client-statement');h.session.access_token='rotated-token';
 pending.resolve({client:{client_id:clientId,client_name:'Current protected statement'},loans:[],payments:[]});await flush();
 assert.equal(h.root.querySelector('#client-support-form'),form);assert.equal(message.value,'Same owner private draft');
 assert.match(h.root.querySelector('[data-client-region="statement"]').textContent,/Current protected statement/);
 assert.equal(h.count('/api/v1/client/statement'),1);
});
