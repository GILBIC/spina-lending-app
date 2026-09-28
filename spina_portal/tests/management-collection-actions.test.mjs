import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
const module=await import('../assets/management-collection-actions.js').catch(()=>({}));
const LOAN='11111111-1111-4111-8111-111111111111';
const TX='22222222-2222-4222-8222-222222222222';
const permissions=['lending.contract_collection.activate','lending.no_collection.manage','collection.void.unremitted'];
const tick=async()=>{await setImmediate();await setImmediate();};
const set=(root,name,value)=>{const input=root.querySelector(`[name="${name}"]`);assert.ok(input,name);input.value=value;};
const submit=async(root,selector)=>{const form=root.querySelector(selector);assert.ok(form,selector);fire(form,'submit');await tick();};
async function harness(t,request,grants=permissions){
 assert.equal(typeof module.mountManagementCollectionActions,'function');
 const root=new Element();const calls=[];const controller=new AbortController();
 const dispose=module.mountManagementCollectionActions({root,session:{user:{role:'management'},permissions:grants},signal:controller.signal,api:{request:async(path,options={})=>{calls.push({path,options});return request(path,options);}},confirm:()=>true});
 t.after(dispose);await tick();return {root,calls,controller};
}
test('contract activation uses current server readiness and confirmed evidence',async t=>{
 const h=await harness(t,(path,options)=>options.method==='POST'?{loan_id:LOAN,is_active:true}:{permission:true,loans:[{loan_id:LOAN,client_name:'Borrower',loan_number:'LN-1',can_activate:true,can_deactivate:false,blockers:[]}]},['lending.contract_collection.activate']);
 set(h.root,'activation_note','Verified signed contract');await submit(h.root,'[data-contract-activate]');
 const post=h.calls.find(call=>call.options.method==='POST');assert.equal(post.path,`/api/v1/management/financial-accounting/contract-collection-activation/${LOAN}/activate`);assert.deepEqual(post.options.body,{activation_note:'Verified signed contract',confirm_action:true});assert.equal(post.options.financial,true);
});
test('blocked contract readiness exposes the reason and sends no mutation',async t=>{
 const h=await harness(t,()=>({permission:true,loans:[{loan_id:LOAN,client_name:'Borrower',can_activate:false,can_deactivate:false,blockers:['Signed schedule missing']}]}),['lending.contract_collection.activate']);
 assert.match(h.root.textContent,/Signed schedule missing/);assert.equal(h.root.querySelector('[data-contract-activate]'),null);assert.equal(h.calls.some(call=>call.options.method==='POST'),false);
});
test('No Collection requires a matching preview and submits the loaded operational revision',async t=>{
 const h=await harness(t,(path,options)=>{
  if(path.includes('/management/loans?'))return {loans:[{loan_id:LOAN,client_name:'Borrower',loan_number:'LN-1'}]};
  if(path.includes('/no-collection/loans/'))return {loan_id:LOAN,client_name:'Borrower',operational_version:7,active_no_collection:[]};
  if(path.endsWith('/preview'))return {loan_id:LOAN,operational_version:7,no_collection_date:options.body.no_collection_date,shifts:[{installment_number:1,prior_effective_due_date:'2026-10-01',new_effective_due_date:'2026-10-02'}]};
  return {loans:[{loan_id:LOAN,resulting_operational_version:8}]};
 },['lending.no_collection.manage']);
 set(h.root,'query','Borrower');await submit(h.root,'[data-no-collection-search]');fire(h.root.querySelector('[data-no-collection-loan]'),'click');await tick();
 set(h.root,'no_collection_date','2026-10-01');set(h.root,'reason','Office closed');
 await submit(h.root,'[data-no-collection-declare]');assert.equal(h.calls.some(call=>call.path.endsWith('/no-collection')&&call.options.method==='POST'),false);
 fire(h.root.querySelector('[data-no-collection-preview]'),'click');await tick();assert.match(h.root.textContent,/2026-10-02/);
 await submit(h.root,'[data-no-collection-declare]');const post=h.calls.find(call=>call.path.endsWith('/no-collection')&&call.options.method==='POST');
 assert.deepEqual(post.options.body,{no_collection_date:'2026-10-01',reason:'Office closed',loans:[{loan_id:LOAN,expected_operational_version:7}]});assert.equal(post.options.financial,true);
});
test('void lookup binds the receipt, and uncertain mutations lock further writes',async t=>{
 const h=await harness(t,(path,options)=>{if(options.method==='POST')throw Object.assign(new Error('Timeout'),{status:503});return {transaction_id:TX,receipt_number:'RCPT-1',client_name:'Borrower',amount:'100.15',is_locked:false,is_voided:false};},['collection.void.unremitted']);
 set(h.root,'receipt_number','RCPT-1');await submit(h.root,'[data-void-search]');set(h.root,'void_reason','Entered twice');await submit(h.root,'[data-void-save]');
 assert.match(h.root.textContent,/not confirm|Refresh/i);await submit(h.root,'[data-void-save]');
 const posts=h.calls.filter(call=>call.options.method==='POST');assert.equal(posts.length,1);assert.equal(posts[0].path,`/api/v1/management/collections/${TX}/void`);assert.deepEqual(posts[0].options.body,{reason:'Entered twice'});
});
test('permissions and disposal prevent unauthorized or late private controls',async t=>{
 const denied=await harness(t,()=>{throw new Error('No reads expected');},[]);assert.equal(denied.calls.length,0);assert.equal(denied.root.querySelector('form'),null);
 let resolve;const h=await harness(t,()=>new Promise(done=>{resolve=done;}),['lending.contract_collection.activate']);h.controller.abort();resolve({permission:true,loans:[{loan_id:LOAN,client_name:'Late private',can_activate:true}]});await tick();assert.equal(h.root.innerHTML,'');
});
import {mountManagementWorkspace} from '../assets/roles/management.js';
test('Management workspace wires permitted collection actions and disposes old controls on remount',async t=>{
 const root=new Element(),controller=new AbortController(),calls=[],navigation=[];
 const context={root,signal:controller.signal,session:{user:{role:'management'},permissions:['lending.contract_collection.activate']},setNavigation:items=>navigation.push(items),api:{request:async(path,options={})=>{calls.push({path,options});return path.endsWith('/contract-collection-activation')?{permission:true,loans:[{loan_id:LOAN,client_name:'Borrower',loan_number:'LN-1',can_activate:true}]}:{};}}};
 t.after(()=>controller.abort());await mountManagementWorkspace(context);await tick();
 assert.ok(navigation[0].some(item=>item.id==='management-collection-actions'));const oldForm=root.querySelector('[data-contract-activate]');assert.ok(oldForm);set(oldForm,'activation_note','Old view');
 context.session={user:{role:'management'},permissions:[]};await mountManagementWorkspace(context);fire(oldForm,'submit');await tick();
 assert.equal(root.querySelector('[data-management-collection-actions]'),null);assert.equal(calls.some(call=>call.options.method==='POST'),false);
});

test('No Collection preview cannot be reused after date changes; reversal uses loaded revision',async t=>{
 const adjustment='33333333-3333-4333-8333-333333333333';
 const h=await harness(t,(path,options)=>{
  if(path.includes('/management/loans?'))return {loans:[{loan_id:LOAN,client_name:'Borrower'}]};
  if(path.includes('/no-collection/loans/'))return {loan_id:LOAN,client_name:'Borrower',operational_version:7,active_no_collection:[{adjustment_id:adjustment,no_collection_date:'2026-09-29',reason:'Closed'}]};
  if(path.endsWith('/preview'))return {loan_id:LOAN,operational_version:7,no_collection_date:options.body.no_collection_date,shifts:[{installment_number:1,prior_effective_due_date:'2026-10-01',new_effective_due_date:'2026-10-02'}]};
  return {loan_id:LOAN,reverses_adjustment_id:adjustment,resulting_operational_version:8};
 },['lending.no_collection.manage']);
 set(h.root,'query','Borrower');await submit(h.root,'[data-no-collection-search]');fire(h.root.querySelector('[data-no-collection-loan]'),'click');await tick();
 set(h.root,'no_collection_date','2026-10-01');fire(h.root.querySelector('[data-no-collection-preview]'),'click');await tick();set(h.root,'no_collection_date','2026-10-02');fire(h.root.querySelector('[name="no_collection_date"]'),'input');set(h.root,'reason','Closed');await submit(h.root,'[data-no-collection-declare]');assert.equal(h.calls.some(call=>call.options.financial),false);
 set(h.root,'reversal_reason','Office reopened');await submit(h.root,'[data-no-collection-reverse]');const post=h.calls.find(call=>call.options.financial);assert.equal(post.path,`/api/v1/management/no-collection/${adjustment}/reverse`);assert.deepEqual(post.options.body,{expected_operational_version:7,reason:'Office reopened'});
});
for(const code of [401,403,426])test(`collection denial ${code} erases private evidence and leaves a terminal explanation`,async t=>{
 const h=await harness(t,(_path,options)=>{if(options.method)throw Object.assign(new Error('Private backend detail'),{status:code});return {permission:true,loans:[{loan_id:LOAN,client_name:'Private borrower',can_activate:true}]};},['lending.contract_collection.activate']);
 const form=h.root.querySelector('[data-contract-activate]');set(form,'activation_note','Reviewed');fire(form,'submit');await tick();
 assert.doesNotMatch(h.root.textContent,/Private borrower|Private backend detail/);assert.match(h.root.textContent,/sign in|update/i);assert.equal(h.root.querySelector('form'),null);fire(form,'submit');await tick();assert.equal(h.calls.filter(call=>call.options.method).length,1);
});
