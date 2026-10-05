import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {mountOfficeOnboarding} from '../assets/office-onboarding.js';
import {bindEmployeeOfficeCase} from '../assets/employee-office-case.js';

const session = {user:{id:'staff',role:'employee'},permissions:['client_onboarding.requirement.review']};
const record = reference => ({applicant_id:'11111111-1111-4111-8111-111111111111',application_reference:reference,
 status:'under_verification',client_id:null,full_name:'Saved applicant',phone_number:'00000000000',present_address:'Saved address',email:null,
 privacy_consent:true,accuracy_declaration:true,bypassed_requirements:[],bypass_reason:null,
 requirements:Object.fromEntries(['national_id','tin_id','meralco_bill','collector_visit'].map(name=>[name,{status:'pending',evidence_reference:null,note:null}]))});
function harness(confirmDiscard=()=>false) {
 const root=new Element();root.innerHTML='<section id="employee-onboarding"><div data-intake></div></section><section id="employee-cif-review"><input name="applicationReference" /></section>';
 const calls=[];let resolve;
 const h={root,calls,read:async path=>record(decodeURIComponent(path.split('/').at(-2))),pending:()=>new Promise(done=>resolve=done),resolve:value=>resolve(value)};
 h.binding=bindEmployeeOfficeCase({root,navigate(){},getSession:()=>session,confirmDiscard});
 h.dispose=mountOfficeOnboarding({root:root.querySelector('[data-intake]'),api:{request(path,options={}){calls.push({path,options});return h.read(path);}},session,
  officeCaseContext:h.binding.coordinator,registerHandle:handle=>h.binding.coordinator?.registerStage('intake',handle)});
 h.binding.activate('intake');return h;
}
const lookup=h=>h.root.querySelector('[data-case-lookup]');
const field=(h,name)=>h.root.querySelector('#employee-onboarding').querySelector(`[name="${name}"]`);
async function open(h,reference='INTAKE-A'){field(h,'applicationReference').value=reference;fire(field(h,'applicationReference'),'input');fire(lookup(h),'submit');await setImmediate();}
test('lookup_edit_keeps_unsaved_intake_and_live_controls',async()=>{
 const h=harness();fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();
 const name=field(h,'full_name'),consent=field(h,'privacy_consent');name.value='Unfinished';consent.checked=true;
 field(h,'applicationReference').value='OTHER';fire(field(h,'applicationReference'),'input');fire(field(h,'applicationReference'),'change');
 assert.equal(field(h,'full_name'),name);assert.equal(name.value,'Unfinished');assert.equal(consent.checked,true);assert.equal(h.calls.length,0);h.dispose();h.binding.dispose();
});
test('new_intake_never_carries_previous_case_to_cif',async()=>{
 const h=harness();await open(h);fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();h.binding.activate('cif');await setImmediate();
 assert.equal(h.root.querySelector('#employee-cif-review').querySelector('input').value,'');assert.equal(field(h,'applicationReference').value,'');
 assert.equal(h.calls.filter(call=>call.options.method&&call.options.method!=='GET').length,0);h.dispose();h.binding.dispose();
});
test('cancel_discard_keeps_exact_dom_and_selection',async()=>{
 let confirmations=0;const h=harness(()=>{confirmations++;return false;});await open(h);const decision=field(h,'tin_id_status');decision.value='failed';fire(decision,'change');
 await open(h,'INTAKE-B');assert.equal(field(h,'tin_id_status'),decision);assert.equal(decision.value,'failed');assert.match(h.root.textContent,/Saved applicant/);
 assert.equal(confirmations,1);assert.equal(h.binding.coordinator.getContext().intakeReference,'INTAKE-A');
 assert.equal(h.calls.filter(call=>call.options.method&&call.options.method!=='GET').length,0);h.dispose();h.binding.dispose();
});
test('stale_lookup_cannot_commit_replacement',async()=>{
 const h=harness(()=>true);await open(h);const original=field(h,'tin_id_status');original.value='passed';h.read=h.pending;
 field(h,'applicationReference').value='INTAKE-B';fire(lookup(h),'submit');await setImmediate();
 field(h,'applicationReference').value='INTAKE-C';fire(field(h,'applicationReference'),'input');h.resolve(record('INTAKE-B'));await setImmediate();
 assert.equal(field(h,'tin_id_status'),original);assert.equal(original.value,'passed');assert.match(h.root.textContent,/Saved applicant/);
 assert.equal(h.calls.filter(call=>call.options.method&&call.options.method!=='GET').length,0);h.dispose();h.binding.dispose();
});
test('same-case lookup cannot remove an unfinished requirement decision',async()=>{
 const h=harness(()=>true);await open(h);const original=field(h,'tin_id_status');original.value='failed';fire(original,'change');
 await open(h);assert.equal(field(h,'tin_id_status'),original);assert.equal(original.value,'failed');h.dispose();h.binding.dispose();
});
test('verified intake save with a failed follow-up read retains its reference and read-only recovery',async()=>{
 const h=harness();fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();
 for(const [name,value] of Object.entries({full_name:'Unfinished applicant',phone_number:'00000000000',present_address:'Saved address',national_id_egov_evidence_reference:'External',tin_id_egov_evidence_reference:'External',meralco_bill_evidence_reference:'External'}))field(h,name).value=value;
 field(h,'privacy_consent').checked=true;field(h,'accuracy_declaration').checked=true;
 let calls=0;h.read=async()=>{if(calls++===0)return {application_reference:'INTAKE-SAVED',status:'requirements_incomplete'};throw Error('Read unavailable');};
 fire(h.root.querySelector('[data-intake-form]'),'submit');await setImmediate();
 assert.equal(h.binding.coordinator.getContext().intakeReference,'INTAKE-SAVED');assert.match(h.root.textContent,/saved.*details.*unavailable/i);assert.ok(h.root.querySelector('[data-reload-case]'));
 h.read=async()=>record('INTAKE-SAVED');fire(h.root.querySelector('[data-reload-case]'),'click');await setImmediate();
 assert.equal(field(h,'applicationReference').value,'INTAKE-SAVED');assert.equal(h.calls.filter(call=>call.options.method==='POST').length,1);h.dispose();h.binding.dispose();
});
test('empty Clear search preserves unsaved intake text and checkboxes without reads',async()=>{
 const h=harness();fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();const name=field(h,'full_name'),consent=field(h,'privacy_consent');name.value='Unsaved';consent.checked=true;
 const clear=h.root.querySelector('[data-clear-intake-search]');assert.ok(clear,'A distinct Clear search action is available');fire(clear,'click');fire(clear,'click');
 assert.equal(field(h,'full_name'),name);assert.equal(name.value,'Unsaved');assert.equal(consent.checked,true);assert.equal(h.calls.length,0);h.dispose();h.binding.dispose();
});
for(const action of ['data-new-intake','data-clear-case'])test(`cancelled ${action} preserves intake values and initiating focus`,async()=>{
 const h=harness();fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();const name=field(h,'full_name');name.value='Unsaved';fire(name,'input');const button=h.root.querySelector(`[${action}]`);fire(button,'click');await setImmediate();
 assert.equal(field(h,'full_name'),name);assert.equal(name.value,'Unsaved');assert.equal(h.binding.coordinator.getContext().mode,'new-intake');assert.equal(button.focused,true);h.dispose();h.binding.dispose();
});
for(const status of [404,'network'])test(`intake candidate ${status} preserves old authorized requirement edits`,async()=>{
 const h=harness();await open(h);const decision=field(h,'tin_id_status');decision.value='failed';fire(decision,'change');h.read=async()=>{throw Object.assign(Error('Unavailable'),{status});};await open(h,'INTAKE-B');assert.equal(field(h,'tin_id_status'),decision);assert.equal(decision.value,'failed');assert.equal(h.binding.coordinator.getContext().intakeReference,'INTAKE-A');assert.equal(h.calls.filter(c=>c.options.method&&c.options.method!=='GET').length,0);h.dispose();h.binding.dispose();
});
test('further intake edits revoke an awaited discard decision',async()=>{
 let consent;const h=harness(()=>new Promise(resolve=>consent=resolve));await open(h);const decision=field(h,'tin_id_status');decision.value='failed';fire(decision,'change');await open(h,'INTAKE-B');decision.value='passed';fire(decision,'change');consent(true);await setImmediate();assert.equal(field(h,'tin_id_status'),decision);assert.equal(decision.value,'passed');assert.equal(h.binding.coordinator.getContext().intakeReference,'INTAKE-A');h.dispose();h.binding.dispose();
});

test('delayed intake submit protects New Open Close and read-only Refresh through uncertainty',async()=>{
 const h=harness(()=>true);fire(h.root.querySelector('[data-new-intake]'),'click');await setImmediate();
 for(const [name,value] of Object.entries({full_name:'Synthetic pending',phone_number:'00000000000',present_address:'Synthetic address',national_id_egov_evidence_reference:'External',tin_id_egov_evidence_reference:'External',meralco_bill_evidence_reference:'External'}))field(h,name).value=value;
 field(h,'privacy_consent').checked=true;field(h,'accuracy_declaration').checked=true;
 let reject;h.read=()=>new Promise((_,no)=>reject=no);const form=h.root.querySelector('[data-intake-form]'),name=field(h,'full_name');fire(form,'submit');await setImmediate();
 for(const kind of ['new-intake','open','close'])assert.equal(await h.binding.coordinator.requestTransition({kind,candidate:{mode:'saved-case',intakeReference:'OTHER'}}),false);
 assert.equal(await h.binding.coordinator.refreshReadOnly('intake'),false);assert.equal(h.binding.coordinator.isWritePending(),true);
 assert.equal(field(h,'full_name'),name);assert.equal(name.value,'Synthetic pending');
 reject(Error('Lost original intake'));await setImmediate();
 assert.equal(h.binding.coordinator.isWritePending(),true);assert.equal(await h.binding.coordinator.requestTransition({kind:'close'}),false);fire(form,'submit');await setImmediate();
 assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);h.dispose();h.binding.dispose();
});
