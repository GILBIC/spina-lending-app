import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { Element, fire } from './helpers/dom.mjs';
import { mountOfficeCifWorkflow } from '../assets/office-cif-workflow.js';
const clientId='11111111-1111-4111-8111-111111111111';
const cifVersionId='22222222-2222-4222-8222-222222222222';
const evidenceId='33333333-3333-4333-8333-333333333333';
const identity={birth_date:'1990-01-02',birth_place:'Synthetic town',civil_status:null,citizenship:null};
const information={full_name:'Synthetic applicant',phone_number:'09171111111',email:null,present_address:'Synthetic address',identity_information:identity};
const summary={client_id:clientId,cif_version_id:cifVersionId,version_number:3,status:'draft',review_scope:'cif_information_only',...information};
function harness(role='employee') {
 const root=new Element();const calls=[];const controller=new AbortController();
 const options={root,clientId,signal:controller.signal,session:{user:{role},permissions:['client_onboarding.requirement.review']},api:{async request(path,options={}){
  calls.push({path,options});
  if(path.includes('review-summary'))return summary;
  if(path.includes('privacy'))return {issuance_ready:false};
  if(path.includes('/context'))return {client_id:clientId,cif_version_id:cifVersionId,purpose:'cif_review',snapshot_sha256:'a'.repeat(64)};
  if(path.includes('/review-evidence?'))return {evidence_id:evidenceId,evidence_reference:`office-evidence:${evidenceId}`,client_id:clientId,cif_version_id:cifVersionId,purpose:'cif_review',snapshot_sha256:'a'.repeat(64)};
  if(path.includes('review-confirmations'))return {review_confirmation_id:evidenceId,client_id:clientId,cif_version_id:cifVersionId};
  return {client_id:clientId,version_number:3,liveness_status:'passed',status:'active'};
 }}};
 return {root,calls,controller,options};
}
test('mounted review signs exact extended facts and disposes private panels on abort',async()=>{
 const h=harness();mountOfficeCifWorkflow(h.options);assert.equal(h.calls.length,0);
 fire(h.root.querySelector('[data-open-cif-workflow]'),'click');await setImmediate();
 assert.match(h.root.textContent,/Synthetic town/);
 assert.equal(h.root.querySelector('[data-confirm-cif]').disabled,true);
 h.root.querySelector('[name="signedScan"]').files=[{type:'application/pdf',size:48}];
 h.root.querySelector('[name="witnessed"]').checked=true;
 fire(h.root.querySelector('[data-signed-cif]').querySelector('form'),'submit');await setImmediate();
 fire(h.root.querySelector('[data-confirm-cif]'),'click');await setImmediate();
 const confirm=h.calls.find(call=>call.path.endsWith('review-confirmations'));
 assert.deepEqual(confirm.options.body.expected_information,information);
 assert.equal(confirm.options.body.applicant_confirmation_evidence_reference,`office-evidence:${evidenceId}`);
 assert.equal(h.root.querySelector('[data-activate-cif]'),null);
 h.controller.abort();assert.equal(h.root.innerHTML,'');
});
test('Management activation and provider result explicitly bind the selected version',async()=>{
 const h=harness('management');mountOfficeCifWorkflow(h.options);
 fire(h.root.querySelector('[data-open-cif-workflow]'),'click');await setImmediate();
 h.root.querySelector('[name="providerReference"]').value='controlled-provider-result';h.root.querySelector('[name="providerPassed"]').checked=true;
 fire(h.root.querySelector('[data-baseline-cif]'),'submit');await setImmediate();
 fire(h.root.querySelector('[data-activate-cif]'),'click');await setImmediate();
 for(const suffix of ['baseline-live-face','activate'])assert.equal(h.calls.find(call=>call.path.endsWith(suffix)).options.body.cif_version_id,cifVersionId);
 assert.match(h.root.textContent,/CIF activated/);
});
test('nonoffice mount exposes no actions or source requests',()=>{
 const h=harness('collector');mountOfficeCifWorkflow(h.options);assert.equal(h.root.querySelector('button'),null);assert.equal(h.calls.length,0);
});
