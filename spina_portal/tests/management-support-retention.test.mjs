import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const session={user:{id:'manager'},permissions:['support.manage']};
const id=i=>`00000000-0000-4000-8000-${String(i).padStart(12,'0')}`;
const row=i=>({request_id:id(i),client_id:id(100+i),status:'open',subject:`Question ${i}`,message:'Question text',management_response:null,responded_at:null});
async function setup(api,extra={}){const mod=await import('../assets/management-support.js').catch(()=>({}));assert.ok(mod.mountManagementSupport);const root=new Element();const h=mod.mountManagementSupport({root,api,getSession:()=>session,...extra});await h.refresh();return{root,h};}
test('saving one response preserves another mounted response and does not remount the queue',async()=>{
 const records=[row(1),row(2)],calls=[];let saved=false;
 const {root,h}=await setup({async request(path,options){calls.push([path,options]);if(options?.method){saved=true;return {request:{...row(1),status:'answered',management_response:'Confirmed response',responded_at:'2026-10-02T01:00:00Z'}};}return {requests:records};}});
 const forms=root.querySelectorAll('[data-support-form]');const draft=forms[1].querySelector('[name="response"]');draft.value='Unsent other row';forms[0].querySelector('[name="response"]').value='Confirmed response';fire(forms[0],'submit');await tick();
 assert.equal(saved,true);assert.equal(root.querySelectorAll('[data-support-form]')[1].querySelector('[name="response"]'),draft);assert.equal(draft.value,'Unsent other row');assert.match(root.textContent,/Response saved/);assert.equal(calls.filter(([,o])=>o?.method==='POST').length,1);h.dispose();
});
test('malformed success freezes both duplicate submission and ordinary refresh; explicit reconciliation stays blocked without exact evidence',async()=>{
 let posts=0;const {root,h}=await setup({async request(path,options){if(options?.method){posts++;return {};}return {requests:[row(1)]};}});
 const form=root.querySelector('[data-support-form]');form.querySelector('[name="response"]').value='Review response';fire(form,'submit');await tick();fire(form,'submit');await tick();assert.equal(posts,1);assert.equal(h.isWritePending(),true);assert.equal(await h.refresh(),false);
 fire(root.querySelector('[data-support-reconcile]'),'click');await tick();assert.equal(h.isWritePending(),true);assert.equal(posts,1);h.dispose();
});
test('dirty queue filter requires deliberate discard and changed preflight never posts',async()=>{
 let changed=false,posts=0;const previous=globalThis.confirm;globalThis.confirm=()=>false;
 try{const {root,h}=await setup({async request(path,options){if(options?.method)posts++;return {requests:[{...row(1),status:changed?'answered':'open'}]};}});const form=root.querySelector('[data-support-form]');form.querySelector('[name="response"]').value='Unsent response';const filter=root.querySelector('[data-support-status]');filter.value='resolved';fire(filter,'change');await tick();assert.equal(filter.value,'open');assert.equal(root.querySelector('[data-support-form]'),form);changed=true;fire(form,'submit');await tick();assert.equal(posts,0);assert.match(root.textContent,/changed/);h.dispose();}finally{globalThis.confirm=previous;}
});
