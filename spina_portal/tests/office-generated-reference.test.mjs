import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountOfficeApplicationReview} from '../assets/office-application-review.js';
import {bindEmployeeOfficeCase} from '../assets/employee-office-case.js';

const client='11111111-1111-4111-8111-111111111111';
const cif='22222222-2222-4222-8222-222222222222';

test('Employee Office Next carries the generated reference without resetting its application draft',async t=>{
  const root=new Element();root.innerHTML='<section id="employee-application-review"><div data-review></div></section><section id="employee-first-loan"><input name="intakeReference" /><input name="applicationReference" /></section>';
  const review=root.querySelector('[data-review]'),calls=[];
  const session={user:{role:'employee'},permissions:['client_onboarding.requirement.review']};
  const office=bindEmployeeOfficeCase({root,navigate(){},getSession:()=>session});t.after(()=>office.dispose());
  const dispose=mountOfficeApplicationReview({root:review,session,officeCaseContext:office.coordinator,onContextChange:value=>office.coordinator.acceptVerifiedContext(value,office.coordinator.getGeneration()),api:{async request(path,options){calls.push({path,options});return path.endsWith('/cif-client')?{application_reference:'CASE-1',client_id:client}:{client_id:client,cif_version_id:cif,cif_version_number:1,loan_types:[]};}}});t.after(dispose);
  await office.activate('application');
  const intake=review.querySelector('[name="intakeReference"]');intake.value='CASE-1';fire(intake,'input');
  fire(review.querySelector('[data-new-application]'),'click');await setImmediate();
  const reference=review.querySelector('[name="applicationReference"]').value,purpose=review.querySelector('[name="purpose"]');purpose.value='Retained generated application';
  await office.activate('first-loan');const target=root.querySelector('#employee-first-loan');
  assert.match(reference,/^LOAN-/);assert.equal(target.querySelector('[name="applicationReference"]').value,reference);assert.equal(target.querySelector('[name="intakeReference"]').value,'CASE-1');
  assert.strictEqual(review.querySelector('[name="purpose"]'),purpose);assert.equal(purpose.value,'Retained generated application');assert.equal(calls.length,2);assert.ok(calls.every(call=>!call.options?.method));
  assert.equal(office.coordinator.getContext().applicationSaved,false);assert.equal(office.coordinator.getContext().applicationId,null);assert.equal(office.coordinator.getContext().applicationVersionId,null);assert.match(target.textContent,/Draft reference — not saved/);
});

for(const role of ['management','employee']) test(`${role}: New application generates one reference and preserves its draft on repeated clicks`,async t=>{
  const root=new Element(),calls=[];let resolve;
  const dispose=mountOfficeApplicationReview({root,session:{user:{role},permissions:['client_onboarding.requirement.review']},api:{async request(path,options){
    calls.push({path,options});
    if(path.endsWith('/cif-client'))return new Promise(done=>{resolve=done;});
    return {client_id:client,cif_version_id:cif,cif_version_number:1,loan_types:[]};
  }}});t.after(dispose);
  root.querySelector('[name="intakeReference"]').value='CASE-1';
  const button=root.querySelector('[data-new-application]');
  fire(button,'click');fire(button,'click');
  assert.equal(calls.length,1,'Double click starts only one intake lookup');
  resolve({application_reference:'CASE-1',client_id:client});await setImmediate();
  const reference=root.querySelector('[name="applicationReference"]').value;
  assert.match(reference,/^LOAN-[0-9a-f-]{36}$/i);
  const purpose=root.querySelector('[name="purpose"]');assert.ok(purpose);
  purpose.value='Retain this application draft';
  fire(button,'click');await setImmediate();
  assert.equal(root.querySelector('[name="applicationReference"]').value,reference);
  assert.equal(root.querySelector('[name="purpose"]'),purpose);
  assert.equal(purpose.value,'Retain this application draft');
  assert.equal(calls.length,2,'An existing draft is not recreated or reloaded');
  assert.ok(calls.every(call=>!call.options?.method),'Opening a draft never saves an application');
});

test('failed intake lookup allocates nothing; context retry retains the generated reference',async t=>{
  const root=new Element();let failLookup=true;
  const dispose=mountOfficeApplicationReview({root,session:{user:{role:'management'},permissions:['client_onboarding.requirement.review']},api:{async request(path){
    if(path.endsWith('/cif-client')){if(failLookup)throw Error('Synthetic read failure');return {application_reference:'CASE-1',client_id:client};}
    throw Error('Synthetic context failure');
  }}});t.after(dispose);
  root.querySelector('[name="intakeReference"]').value='CASE-1';
  const button=root.querySelector('[data-new-application]');
  fire(button,'click');await setImmediate();assert.equal(root.querySelector('[name="applicationReference"]').value,'');
  failLookup=false;fire(button,'click');await setImmediate();
  const reference=root.querySelector('[name="applicationReference"]').value;assert.match(reference,/^LOAN-/);
  fire(button,'click');await setImmediate();assert.equal(root.querySelector('[name="applicationReference"]').value,reference);
});

for(const failure of ['rejected','stale'])test(`${failure} generated draft publication preserves selected identity and offers local recovery`,async t=>{
 const root=new Element();root.innerHTML='<section id="employee-application-review"><div data-review></div></section>';
 const review=root.querySelector('[data-review]'),session={user:{id:'staff',role:'employee'},permissions:['client_onboarding.requirement.review']},calls=[];let resolve;
 const office=bindEmployeeOfficeCase({root,navigate(){},getSession:()=>session});t.after(()=>office.dispose());
 const dispose=mountOfficeApplicationReview({root:review,session,officeCaseContext:office.coordinator,onContextChange:value=>office.coordinator.acceptVerifiedContext(value,office.coordinator.getGeneration()),api:{async request(path,options){calls.push({path,options});if(path.endsWith('/cif-client'))return new Promise(done=>resolve=done);return {client_id:client,cif_version_id:cif,cif_version_number:1,loan_types:[]};}}});t.after(dispose);
 await office.activate('application');office.coordinator.acceptVerifiedContext({mode:'saved-case',intakeReference:'CASE-A',clientId:client,applicationReference:'APP-A',applicationSaved:true},office.coordinator.getGeneration());
 const intake=review.querySelector('[name="intakeReference"]'),application=review.querySelector('[name="applicationReference"]'),button=review.querySelector('[data-new-application]');
 intake.value=failure==='rejected'?'CASE-B':'CASE-A';fire(button,'click');
 if(failure==='stale')office.coordinator.invalidateCandidate();resolve({application_reference:intake.value,client_id:client});await setImmediate();
 assert.equal(office.coordinator.getContext().intakeReference,'CASE-A');assert.equal(office.coordinator.getContext().applicationReference,'APP-A');assert.equal(application.value,'');assert.equal(review.querySelector('[name="purpose"]'),null);
 const status=review.querySelector('[data-application-review-status]');assert.doesNotMatch(status.textContent,/Loading application entry/);assert.match(status.textContent,/selected case|selected intake/i);assert.match(status.textContent,/try|return|close/i);assert.equal(button.disabled,false);assert.equal(calls.length,1);assert.ok(calls.every(call=>!call.options?.method));
 intake.value='CASE-A';fire(button,'click');resolve({application_reference:'CASE-A',client_id:client});await setImmediate();assert.ok(review.querySelector('[name="purpose"]'));assert.match(application.value,/^LOAN-/);assert.equal(office.coordinator.getContext().applicationSaved,false);assert.ok(calls.every(call=>!call.options?.method));
});
