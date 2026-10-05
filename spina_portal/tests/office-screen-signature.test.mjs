import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {prepareSignature} from './helpers/signature.mjs';
import {mountOfficeEvidenceCapture} from '../assets/office-evidence-capture.js';

const CLIENT='11111111-1111-4111-8111-111111111111', CIF='22222222-2222-4222-8222-222222222222', ID='33333333-3333-4333-8333-333333333333';
async function harness(options={}) {
 const root=new Element(),calls=[],controller=new AbortController();let captured;
 const context={client_id:CLIENT,cif_version_id:CIF,purpose:'cif_review',snapshot_sha256:'a'.repeat(64)};
 const api={async request(path,request={}){calls.push({path,...request});if(!request.method)return context;if(options.write)return options.write(path,request);return {...context,evidence_id:ID,evidence_reference:`office-evidence:${ID}`,capture_method:'screen_signature'};}};
 const handle=mountOfficeEvidenceCapture({root,api,session:{user:{role:'employee'},permissions:['client_onboarding.requirement.review']},clientId:CLIENT,cifVersionId:CIF,purpose:'cif_review',signal:controller.signal,onCaptured:value=>captured=value});
 await setImmediate();const pad=prepareSignature(root,options);
 return {root,calls,handle,pad,controller,get captured(){return captured;},submit(){fire(root.querySelector('form'),'submit');},witness(){root.querySelector('[name="witnessed"]').checked=true;}};
}
test('blank or cleared signatures cannot be saved',async()=>{
 const h=await harness();h.witness();h.submit();await setImmediate();assert.equal(h.calls.length,1);
 h.pad.draw();assert.equal(h.handle.isDirty(),true);fire(h.root.querySelector('[data-signature-clear]'),'click');h.witness();h.submit();await setImmediate();
 assert.equal(h.calls.length,1);assert.equal(h.pad.exports,0);h.handle();
});
test('drawn signature saves exact PNG with screen witness and enables confirmation only after acknowledgment',async()=>{
 const h=await harness();h.pad.draw();h.submit();await setImmediate();assert.equal(h.calls.length,1);
 h.witness();h.submit();await setImmediate();assert.equal(h.calls.length,2);
 const query=new URL(h.calls[1].path,'https://test.invalid').searchParams;
 assert.equal(query.get('capture_method'),'screen_signature');assert.equal(query.get('witnessed_screen_signature'),'true');assert.equal(query.has('witnessed_wet_signature'),false);
 assert.equal(h.calls[1].rawBody,h.pad.file);assert.equal(h.captured.evidence_id,ID);assert.equal(h.handle.isDirty(),false);h.handle();
});
test('signature drawing clears a previous witness choice and dirty signature prevents refresh',async()=>{
 const h=await harness();h.witness();h.pad.draw();assert.equal(h.root.querySelector('[name="witnessed"]').checked,false);
 assert.equal(h.handle.refreshReadOnly(),false);assert.equal(h.calls.length,1);h.handle();
});
test('export is a pending write and a closed session prevents a late upload',async()=>{
 const h=await harness({deferExport:true});h.pad.draw();h.witness();h.submit();
 assert.equal(h.handle.isWritePending(),true);h.submit();assert.equal(h.pad.exports,1);
 h.controller.abort();h.pad.finish();await setImmediate();assert.equal(h.calls.length,1);assert.equal(h.root.innerHTML,'');
});
test('uncertain save retries identical image, method and request and locks editing',async()=>{
 const h=await harness({write:()=>{throw new Error('connection lost');}});h.pad.draw();h.witness();h.submit();await setImmediate();
 assert.equal(h.handle.isUncertain(),true);assert.equal(h.root.querySelector('[data-signature-clear]').disabled,true);
 h.pad.draw();h.submit();await setImmediate();assert.equal(h.calls.length,3);assert.equal(h.calls[1].path,h.calls[2].path);assert.equal(h.calls[1].rawBody,h.calls[2].rawBody);assert.equal(h.pad.exports,1);h.handle();
});
test('access denial erases signature and prevents detached drawing callbacks',async()=>{
 const h=await harness({write:()=>{throw Object.assign(new Error('denied'),{status:403});}});h.pad.draw();h.witness();h.submit();await setImmediate();
 const clears=h.pad.clears;h.pad.draw();assert.equal(h.pad.clears,clears);assert.equal(h.root.querySelector('[data-signature-canvas]'),null);assert.equal(h.handle.isDirty(),false);h.handle();
});

for(const status of [413,415]) test(`first ${status} signature rejection permits redraw, but a prior uncertain write stays locked`,async()=>{
 let rejectStatus=status;
 const h=await harness({write:()=>{throw Object.assign(new Error('rejected'),{status:rejectStatus});}});
 h.pad.draw();h.witness();h.submit();await setImmediate();assert.equal(h.handle.isUncertain(),false);assert.equal(h.root.querySelector('[data-signature-clear]').disabled,false);
 rejectStatus=undefined;h.submit();await setImmediate();assert.equal(h.handle.isUncertain(),true);
 rejectStatus=status;h.submit();await setImmediate();assert.equal(h.handle.isUncertain(),true);assert.equal(h.root.querySelector('[data-signature-clear]').disabled,true);h.handle();
});
