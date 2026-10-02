import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {Element,fire} from './helpers/dom.mjs';import {mountTreasuryWorkspace} from '../assets/treasury-workspace.js';
const {examples}=JSON.parse(await readFile(new URL('./fixtures/collector-surplus-backend.json',import.meta.url),'utf8'));
const get=k=>examples.find(e=>e.kind===k),projection=get('staff-workspace-credits').response.data,actor=projection.actor;
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r));};
for(const control of ['recover','retry','surplus-recover','surplus-retry'])test(`shared ${control} completes the exact child recognition draft and prevents a new unchanged POST`,async()=>{
 const root=new Element(),session={user:{id:actor.user_id,role:'management',status:'active'},device_id:'synthetic',device_registered:true,permissions:[]},calls=[];let saved=null,sourceCase=get('collector_count_accept').response.data.result.case,posts=0;
 const generic={contract_version:1,actor,enabled:true,owner_configured:true,blockers:[],claims:[],capabilities:{evidence_upload:true},accounts:projection.accounts.map(a=>({...a,actions:['evidence_upload'],evidence_purposes:['recipient'],balance:null}))};
 const api={request:async(p,o={})=>{calls.push({p,o});if(p==='/api/v1/treasury/workspace')return generic;
  if(p.includes('/collector-surplus/workspace')){const q=new URLSearchParams(p.split('?')[1]),kind=q.get('kind');return {...projection,kind,accounts:projection.accounts.filter(a=>!q.get('account_id')||q.get('account_id')===a.id),items:kind==='cases'?[sourceCase]:[],total_count:kind==='cases'?1:0,totals:{},offset:Number(q.get('offset'))};}
  if(p.includes('/collector-surplus/cases/'))return sourceCase;
  if(p.endsWith('/actions')){posts++;if(!saved){saved=structuredClone(get('collector_surplus_recognize').response.data);saved.request_id=o.body.request_id;sourceCase=saved.result.case;throw Object.assign(Error('Synthetic lost response'),{code:'network_uncertain'});}assert.equal(o.body.request_id,saved.request_id,'retry must use original request');return saved;}
  if(p.includes('/requests/'))return saved;throw Error('Unexpected read '+p);
 }};
 const originalConfirm=globalThis.confirm;globalThis.confirm=()=>true;const handle=mountTreasuryWorkspace({root,api,getSession:()=>session,confirmAction:()=>true});try{await handle.ready;await handle.activate('surplus');fire(root.querySelector('[data-surplus-navigation="cases"]'),'click');await settle();
  const form=root.querySelector('[data-surplus-form="collector_surplus_recognize"]'),body=get('collector_surplus_recognize').command;
  for(const node of form.querySelectorAll('[data-surplus-field]')){const k=node.getAttribute('name');if(body[k]!==undefined){if(node.getAttribute('type')==='checkbox')node.checked=body[k];else node.value=body[k];}}
  const unrelated=root.querySelector('[data-treasury-action="opening_prepare"]').querySelector('[name="reason"]'),file=root.querySelector('[data-surplus-file]'),retained=new Blob(['synthetic retained'],{type:'image/png'});unrelated.value='Separate retained draft';file.files=[retained];
  fire(form,'submit');await settle();assert.equal(posts,1);assert.equal(handle.isWritePending(),true);const original=JSON.stringify(calls.find(c=>c.p.endsWith('/actions')).o.body);
  assert.equal(await handle.refreshReadOnly(),false);fire(root.querySelector(`[data-${control}]`),'click');await settle();assert.equal(handle.isWritePending(),false);assert.equal(posts,control.endsWith('recover')?1:2);assert.ok(form._saved,'originating child must mark exact draft saved');assert.match(root.querySelector('[data-surplus-status]').textContent,/Identified Collector credit recorded/);
  assert.equal(unrelated.value,'Separate retained draft');assert.equal(file.files[0],retained);assert.equal(root.querySelector('[data-surplus-file]'),file);
  const before=posts;fire(form,'submit');await settle();assert.equal(posts,before,'unchanged recognition must not become a new financial request');assert.match(root.querySelector('[data-surplus-status]').textContent,/already recorded/);if(control.endsWith('retry'))assert.equal(JSON.stringify(calls.filter(c=>c.p.endsWith('/actions'))[1].o.body),original);
 }finally{handle();globalThis.confirm=originalConfirm;}
});
