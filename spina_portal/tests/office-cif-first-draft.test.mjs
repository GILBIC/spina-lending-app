import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { Element, fire } from './helpers/dom.mjs';
import { ApiError } from '../assets/api.js';
import { mountOfficeCifSelection } from '../assets/office-cif-selection.js';
const CLIENT='11111111-1111-4111-8111-111111111111';
const CIF='22222222-2222-4222-8222-222222222222';

async function harness(status=409) {
 const root=new Element();const calls=[];let created=false;const controller=new AbortController();
 mountOfficeCifSelection({root,signal:controller.signal,session:{user:{role:'employee'},permissions:['client_onboarding.requirement.review']},api:{async request(path,options={}){
  calls.push({path,options});
  if(path.endsWith('/cif-client'))return {application_reference:'INTAKE-1',client_id:CLIENT};
  if(path.endsWith('/draft')){created=true;return {client_id:CLIENT,version_number:1,status:'draft'};}
  if(!created)throw new ApiError('Current CIF unavailable',{status});
  return {client_id:CLIENT,cif_version_id:CIF,version_number:1,status:'draft',review_scope:'cif_information_only',full_name:'Synthetic first CIF',phone_number:'09170000000',email:null,present_address:'Synthetic address'};
 }}});
 root.querySelector('input').value='INTAKE-1';fire(root.querySelector('form'),'submit');await setImmediate();
 return {root,calls,controller};
}
for(const status of [404,409])test(`${status}: eligible selection requires explicit first draft POST then opens current review`,async()=>{
 const h=await harness(status);assert.equal(h.calls.length,2);assert.equal(h.calls.some(c=>c.options.method==='POST'),false);
 fire(h.root.querySelector('[data-begin-cif]'),'click');await setImmediate();
 assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
 assert.equal(h.calls[2].path,`/api/v1/management/clients/${CLIENT}/cif/draft`);
 assert.match(h.root.textContent,/Synthetic first CIF/);assert.ok(h.root.querySelector('[data-open-cif-workflow]'));
 h.controller.abort();assert.equal(h.root.innerHTML,'');
});
for(const status of [401,403,500])test(`${status}: access or server errors never offer first-draft mutation`,async()=>{
 const h=await harness(status);assert.equal(h.root.querySelector('[data-begin-cif]'),null);assert.equal(h.calls.length,2);h.controller.abort();
});
