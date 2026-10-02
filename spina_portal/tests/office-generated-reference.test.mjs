import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountOfficeApplicationReview} from '../assets/office-application-review.js';

const client='11111111-1111-4111-8111-111111111111';
const cif='22222222-2222-4222-8222-222222222222';

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
