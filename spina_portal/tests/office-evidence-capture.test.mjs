import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { Element, fire } from './helpers/dom.mjs';
const clientId='11111111-1111-4111-8111-111111111111';
const cifVersionId='22222222-2222-4222-8222-222222222222';
const evidenceId='33333333-3333-4333-8333-333333333333';
const session={user:{role:'employee'},permissions:['client_onboarding.requirement.review']};

test('capture requires witnessed file, binds context digest and retries the same request without a manual reference',async()=>{
 const {mountOfficeEvidenceCapture}=await import('../assets/office-evidence-capture.js');
 const root=new Element(); const calls=[];let result;
 const api={async request(path,options={}){calls.push({path,options});
  if(!options.method)return {client_id:clientId,cif_version_id:cifVersionId,purpose:'cif_review',snapshot_sha256:'a'.repeat(64)};
  return {evidence_id:evidenceId,evidence_reference:`office-evidence:${evidenceId}`,client_id:clientId,cif_version_id:cifVersionId,purpose:'cif_review',snapshot_sha256:'a'.repeat(64)};
 }};
 const dispose=mountOfficeEvidenceCapture({root,api,session,clientId,cifVersionId,purpose:'cif_review',onCaptured:value=>result=value});
 await setImmediate();
 fire(root.querySelector('form'),'submit');await setImmediate();assert.equal(calls.length,1);
 root.querySelector('[name="signedScan"]').files=[{type:'application/pdf',size:34}];
 root.querySelector('[name="witnessed"]').checked=true;
 fire(root.querySelector('form'),'submit');await setImmediate();
 assert.equal(calls[1].options.method,'POST');assert.equal(calls[1].options.rawBody.type,'application/pdf');
 assert.match(calls[1].path,/expected_snapshot_sha256=a{64}/);assert.match(calls[1].path,/witnessed_wet_signature=true/);
 assert.equal(result.evidence_reference,`office-evidence:${evidenceId}`);assert.equal(root.querySelector('[name="evidence_reference"]'),null);
 dispose();assert.equal(root.innerHTML,'');
});

test('forbidden office role performs no context lookup',async()=>{
 const {mountOfficeEvidenceCapture}=await import('../assets/office-evidence-capture.js');const root=new Element();
 mountOfficeEvidenceCapture({root,api:{request(){assert.fail('forbidden request');}},session:{...session,user:{role:'collector'}},clientId,cifVersionId,purpose:'cif_review'});
 assert.match(root.textContent,/Office access/);
});
