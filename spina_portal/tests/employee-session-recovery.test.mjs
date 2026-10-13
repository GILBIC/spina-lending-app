import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';
import {mountEmployeeOperations,syncEmployeeOperationsRecovery} from '../assets/employee-operations.js';
import {workspace,SELF,DEVICE} from './helpers/employee-workspace.mjs';
import {readFile} from 'node:fs/promises';

const OTHER='20000000-0000-4000-8000-000000000001';
const tick=async()=>{await setImmediate();await setImmediate();};
async function fixture(t){
 const h={session:{user:{id:SELF,role:'employee',roles:['employee','collector'],permissions:['employee.self_service'],status:'active',device_registered:true},access_token:'synthetic'},value:workspace(),posts:[],root:new Element(),localDevice:DEVICE};
 h.api={sessionStore:{deviceId:()=>h.localDevice},async request(path,options={}){
  if(options.method==='POST'){h.posts.push(structuredClone(options.body));if(h.complete)return h.complete(options.body);throw Object.assign(Error('Synthetic uncertain transport'),{code:'network_uncertain',status:0});}
  return h.value;
 }};
 h.mount=async(whole=false)=>{h.dispose?.();h.root=new Element();const options={root:h.root,api:h.api,session:h.session,getSession:()=>h.session};
  if(whole)h.dispose=await mountEmployeeWorkspace({...options,setNavigation(){},registerWorkspaceHandle:handle=>h.handle=handle});
  else h.dispose=mountEmployeeOperations({...options,onController:handle=>h.handle=handle});
  await tick();
 };
 t.after(()=>h.dispose?.());await h.mount();return h;
}
async function advance(h){
 fire(h.root.querySelector('[data-employee-create="advance_request"]'),'click');
 for(const [name,value] of Object.entries({amount:'1000.10',reason:'Synthetic request',employee_acknowledgment:'I agree',payroll_authorization:'Recorded authorization'}))h.root.querySelector(`[name="${name}"]`).value=value;
 const row=h.root.querySelector('[data-employee-rows="installments"]');row.querySelector('[name="due_date"]').value='2026-10-09';row.querySelector('[name="amount"]').value='1000.10';
 fire(h.root.querySelector('[data-employee-form]'),'submit');await tick();assert.equal(h.handle.isWritePending(),true);
}

test('mounted Employee recovery survives compatible token refresh and remount through role API wrappers',async t=>{
 const h=await fixture(t);await h.mount(true);await advance(h);const original=h.posts[0];
 h.session={...h.session,access_token:'rotated-synthetic',user:{...h.session.user,roles:['collector','employee']}};
 await h.mount(true);assert.equal(h.handle.isWritePending(),true);assert.ok(h.root.querySelector('[data-employee-retry]'));
 assert.equal(h.root.querySelector('[data-employee-create="advance_request"]').disabled,true);assert.equal(h.posts.length,1,'remount must not automatically retry');
 h.complete=command=>({request_id:command.request_id,id:command.id,version:1,status:'pending_review',message:'Saved for review'});
 fire(h.root.querySelector('[data-employee-retry]'),'click');await tick();assert.deepEqual(h.posts,[original,original]);assert.equal(h.handle.isWritePending(),false);
 await h.mount(true);assert.equal(h.root.querySelector('[data-employee-retry]'),null);
});

for(const change of ['actor','local device','server device','employee identity','permissions','status','device registration','server capability'])test(`${change} loss erases recovery and it cannot return when authority is restored`,async t=>{
 const h=await fixture(t);await advance(h);const originalSession=h.session,originalValue=h.value;
 if(change==='actor'){h.session={...h.session,user:{...h.session.user,id:OTHER}};h.value=workspace({actor:{...h.value.actor,user_id:OTHER,employee_id:OTHER}});}
 if(change==='local device')h.localDevice=OTHER;
 if(change==='server device')h.value=workspace({actor:{...h.value.actor,device_id:OTHER}});
 if(change==='employee identity')h.value=workspace({actor:{...h.value.actor,employee_id:OTHER}});
 if(change==='permissions')h.session={...h.session,user:{...h.session.user,permissions:[]}};
 if(change==='status')h.session={...h.session,user:{...h.session.user,status:'suspended'}};
 if(change==='device registration')h.session={...h.session,user:{...h.session.user,device_registered:false}};
 if(change==='server capability')h.value=workspace({capabilities:{...h.value.capabilities,can_self_service:false}});
 await h.mount();assert.equal(h.root.querySelector('[data-employee-retry]'),null);
 h.session=originalSession;h.value=originalValue;h.localDevice=DEVICE;await h.mount();assert.equal(h.root.querySelector('[data-employee-retry]'),null);assert.equal(h.posts.length,1);
});

test('authority loss while a POST is unresolved rejects late uncertainty and never restores its private form',async t=>{
 const h=await fixture(t);let reject;h.complete=()=>new Promise((resolve,fail)=>reject=fail);
 await advance(h);h.session={...h.session,user:{...h.session.user,permissions:[]}};
 reject(Object.assign(Error('Synthetic late uncertainty'),{code:'network_uncertain',status:0}));await tick();
 assert.equal(h.root.querySelector('[data-employee-form]'),null);assert.equal(h.root.querySelector('[data-employee-retry]'),null);
 h.session={...h.session,user:{...h.session.user,permissions:['employee.self_service']}};await h.mount();assert.equal(h.root.querySelector('[data-employee-retry]'),null);
});

test('acknowledged old completion clears shared recovery after compatible remount without another POST',async t=>{
 const h=await fixture(t);let resolve;h.complete=()=>new Promise(done=>resolve=done);await advance(h);const body=h.posts[0];
 h.session={...h.session,access_token:'rotated-synthetic'};await h.mount();const oldRetry=h.root.querySelector('[data-employee-retry]');assert.ok(oldRetry);
 resolve({request_id:body.request_id,id:body.id,version:1,status:'pending_review',message:'Saved for review'});await tick();
 assert.equal(h.handle.isWritePending(),false);assert.equal(h.root.querySelector('[data-employee-retry]'),null);fire(oldRetry,'click');await tick();assert.equal(h.posts.length,1);
 await h.mount();assert.equal(h.root.querySelector('[data-employee-retry]'),null);
});

test('losing a record action grant clears its uncertain command across remount and restored access',async t=>{
 const h=await fixture(t);const payroll={id:OTHER,employee_id:OTHER,version:3,status:'approved',allowed_actions:['payroll_payment'],payload:{net_pay:'1000.10',balance_due:'1000.10'}};
 h.value=workspace({payroll:[payroll],capabilities:{...h.value.capabilities,can_record_payments:true}});await h.mount();
 fire(h.root.querySelector('[data-employee-action="payroll_payment"]'),'click');
 for(const [name,value] of Object.entries({amount:'1000.10',occurred_at:'2026-10-06T12:00',payment_method:'cash',employee_acknowledgment:'Synthetic receipt',result:'completed'}))h.root.querySelector(`[name="${name}"]`).value=value;
 fire(h.root.querySelector('[data-employee-form]'),'submit');await tick();assert.equal(h.posts.length,1);
 const granted=h.value;h.value={...granted,payroll:[{...payroll,allowed_actions:[]}]};await h.mount();assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);
 h.value=granted;await h.mount();assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.equal(h.posts.length,1);
});

test('the app authentication cleanup erases an uncertain command even when the same actor signs in again',async t=>{
 const h=await fixture(t);await advance(h);const source=await readFile(new URL('../assets/app.js',import.meta.url),'utf8');
 const body=source.slice(source.indexOf('function showAuthentication()'),source.indexOf('async function mountCurrentWorkspace()'));
 const module=await import('../assets/employee-operations.js');
 const signOut=new Function('api','clearCashDisbursementRecovery','clearEmployeeOperationsRecovery','refreshController','clearWorkspace','authenticatedApp','authView','loginForm',`${body};return showAuthentication;`)(h.api,()=>{},module.clearEmployeeOperationsRecovery,{stop(){}},()=>h.dispose(),{}, {},new Element());
 signOut();h.session={...h.session,access_token:'same-actor-new-login'};await h.mount();assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.equal(h.posts.length,1);
});

test('refresh authority synchronization immediately clears mounted private drafts and derived Today data',async t=>{
 const h=await fixture(t);h.value=workspace({tasks:[{id:OTHER,employee_id:SELF,version:1,status:'todo',allowed_actions:[],payload:{description:'Synthetic private task'}}]});await h.mount(true);
 fire(h.root.querySelector('[data-employee-create="advance_request"]'),'click');h.root.querySelector('[name="reason"]').value='Synthetic private draft';
 assert.match(h.root.querySelector('[data-employee-today]').textContent,/1 loaded/);
 h.session={...h.session,user:{...h.session.user,permissions:[]}};syncEmployeeOperationsRecovery(h.api,h.session);
 assert.equal(Boolean(h.root.querySelector('[data-employee-form]')),false);assert.doesNotMatch(h.root.querySelector('[data-employee-today]').textContent,/1 loaded/);
});

test('an acknowledged workspace result removes recovery on a compatible remount',async t=>{
 const h=await fixture(t);await advance(h);const body=h.posts[0];
 h.value={...h.value,last_result:{request_id:body.request_id,id:body.id,version:1,status:'pending_review',message:'Saved for review'}};
 h.session={...h.session,access_token:'rotated'};await h.mount();assert.equal(h.handle.isWritePending(),false);assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.equal(h.posts.length,1);
});

const capabilityCommands=[
 {action:'payroll_prepare',collection:'payroll',capability:'can_prepare_payroll',employee:OTHER,fields:{week_start:'2026-10-04',payroll_kind:'weekly',reason:'Synthetic verified work'}},
 {action:'task_save',collection:'tasks',capability:'can_assign_tasks',employee:OTHER,fields:{description:'Synthetic assigned work',due_date:'2026-10-09'}},
 {action:'accounting_prepare',collection:'accounting_preparations',capability:'can_prepare_accounting',employee:null,fields:{preparation_kind:'journal',description:'Synthetic draft',as_of:'2026-10-06',evidence:'Synthetic reviewed evidence'}},
];
async function uncertainCapabilityCommand(t,spec,{create=false}={}){
 const h=await fixture(t);
 const record={id:OTHER,employee_id:spec.employee,version:3,status:'draft',allowed_actions:[spec.action],payload:{...spec.fields}};
 h.value=workspace({[spec.collection]:create?[]:[record],profiles:[{id:SELF,employee_id:OTHER,version:1,status:'active',allowed_actions:[],payload:{full_name:'Synthetic target employee'}}],capabilities:{...h.value.capabilities,[spec.capability]:true}});
 await h.mount();fire(h.root.querySelector(`[data-employee-${create?'create':'action'}="${spec.action}"]`),'click');
 for(const [name,value] of Object.entries(spec.fields))h.root.querySelector(`[name="${name}"]`).value=value;
 if(create&&spec.employee)h.root.querySelector('[name="employee_id"]').value=spec.employee;
 fire(h.root.querySelector('[data-employee-form]'),'submit');await tick();
 assert.equal(h.posts.length,1);assert.equal(h.posts[0].expected_version,create?0:3);assert.equal(h.handle.isWritePending(),true);
 return {h,record};
}

for(const spec of capabilityCommands){
 for(const loss of ['grant removed','target absent'])test(`${spec.action} update recovery erases on ${loss} while global capability remains`,async t=>{
  const {h,record}=await uncertainCapabilityCommand(t,spec),granted=h.value;
  h.value={...granted,[spec.collection]:loss==='target absent'?[]:[{...record,allowed_actions:[]}]};
  h.session={...h.session,access_token:'rotated'};await h.mount();
  assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.equal(h.handle.isWritePending(),false);assert.equal(h.posts.length,1);
  h.value=granted;await h.mount();assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.equal(h.posts.length,1);
 });
 test(`${spec.action} authorized existing update retains the exact retry including global record identity`,async t=>{
  const {h}=await uncertainCapabilityCommand(t,spec);const original=h.posts[0];h.session={...h.session,access_token:'rotated'};await h.mount();
  assert.ok(h.root.querySelector('[data-employee-retry]'));assert.equal(h.posts.length,1);fire(h.root.querySelector('[data-employee-retry]'),'click');await tick();assert.deepEqual(h.posts,[original,original]);
 });
 test(`${spec.action} new create retains the exact retry without an existing target row`,async t=>{
  const {h}=await uncertainCapabilityCommand(t,spec,{create:true});const original=h.posts[0];h.session={...h.session,access_token:'rotated'};await h.mount();
  assert.ok(h.root.querySelector('[data-employee-retry]'));assert.equal(h.posts.length,1);fire(h.root.querySelector('[data-employee-retry]'),'click');await tick();assert.deepEqual(h.posts,[original,original]);
 });
 for(const loss of ['grant removed','target absent'])test(`${spec.action} matching acknowledgment confirms an update before ${loss} rejects recovery`,async t=>{
  const {h,record}=await uncertainCapabilityCommand(t,spec);const command=h.posts[0];
  h.value={...h.value,[spec.collection]:loss==='target absent'?[]:[{...record,allowed_actions:[]}],last_result:{request_id:command.request_id,id:command.id,version:4,status:'accepted',message:'Synthetic update confirmed'}};
  h.session={...h.session,access_token:'rotated'};await h.mount();
  assert.equal(h.handle.isWritePending(),false);assert.equal(Boolean(h.root.querySelector('[data-employee-retry]')),false);assert.match(h.root.querySelector('[data-employee-status]').textContent,/Synthetic update confirmed/);assert.equal(h.posts.length,1);
 });
}
