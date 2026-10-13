import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountAreaManagement} from '../assets/area-management.js';

const CLIENT='11111111-1111-4111-8111-111111111111',OTHER='22222222-2222-4222-8222-222222222222',PHOTO='33333333-3333-4333-8333-333333333333';
const path=`/api/v1/clients/${CLIENT}/photo`;
const client={client_id:CLIENT,client_code:'OLD-1',full_name:'Legacy Unfinanced Client',area_id:'one',area_path:'One',effective_collector:null};
const saved={photo_id:PHOTO,version:1,content_type:'image/jpeg',byte_size:3,uploaded_at:'2026-10-10T00:00:00Z',uploaded_by_user_id:OTHER,content_url:`${path}/content?photo_id=${PHOTO}`};
const metadata=photo=>({client_id:CLIENT,can_upload:true,photo});
const flush=async()=>{await setImmediate();await setImmediate();};
async function harness({permission=true,writeError,holdArea=false}={}){
 const h={root:new Element(),calls:[],discard:false,controller:new AbortController(),session:{user:{id:OTHER,role:'management'},permissions:['area.client.assign','area.manage',...(permission?['client_onboarding.requirement.review']:[])]}};
 h.handle=await mountAreaManagement({root:h.root,signal:h.controller.signal,getSession:()=>h.session,confirmDiscard:()=>h.discard,api:{async request(url,options={}){
  h.calls.push({url,options});if(url==='/api/v1/areas')return {areas:['one','two'].map(area_id=>({area_id,parent_area_id:null,name:area_id==='one'?'One':'Two',full_path:area_id,is_active:true,depth:0}))};
  if(url.startsWith('/api/v1/areas/clients?'))return {clients:[client,{...client,client_id:OTHER,full_name:'Other Client'}]};
  if(url.includes('/area-transfer-preview?')){const result={client_id:CLIENT,old_area_id:'one',new_area_id:'two',timing:'immediate',effective_date:'2026-10-10'};if(holdArea)return new Promise(resolve=>h.resolveArea=()=>resolve(result));return result;}
  if(url.includes('/area-transfer'))return {client_id:CLIENT,old_area_id:'one',new_area_id:'two',timing:'immediate',effective_date:'2026-10-10'};
  if(url.includes('/photo/content?'))return new Blob([new Uint8Array([1,2,3])],{type:'image/jpeg'});
  if(options.method==='POST' && url.startsWith(path)){if(writeError)throw writeError;return metadata(saved);}if(url===path)return metadata(null);throw Error(`Unexpected request ${url}`);
 }}});
 h.dispatch=async(type,target)=>{const event=new Event(type,{cancelable:true});Object.defineProperty(event,'target',{value:target});h.root.dispatchEvent(event);await flush();};
 h.click=selector=>h.dispatch('click',h.root.querySelector(selector));
 h.submit=(selector,values)=>{const form=h.root.querySelector(selector);form.matches=value=>value===selector;form.elements=Object.fromEntries(Object.entries(values).map(([name,value])=>[name,{value}]));return h.dispatch('submit',form);};
 h.select=async()=>{await h.click('[data-area-action="client-transfer"]');await h.submit('[data-area-client-search-form]',{q:'Legacy Unfinanced'});await h.click(`[data-area-client-id="${CLIENT}"]`);};
 h.open=async()=>{await h.select();const button=h.root.querySelector('[data-open-client-photo]');assert.ok(button,'all-client area search must offer photo access for a client without a loan or intake');fire(button,'click');await flush();};
 h.choose=()=>{const input=h.root.querySelector('[data-photo-file]');input.files=[new Blob([new Uint8Array([4,5,6])],{type:'image/jpeg'})];fire(input,'change');};return h;
}

test('Area borrower search uploads the exact client photo without any loan, account or CIF reference',async()=>{
 const h=await harness();await h.open();assert.match(h.root.querySelector('[data-area-client-photo]').textContent,/Legacy Unfinanced Client/);h.choose();fire(h.root.querySelector('[data-photo-save]'),'click');await flush();const writes=h.calls.filter(x=>x.options.method==='POST');assert.equal(writes.length,1);assert.match(writes[0].url,new RegExp(`^${path}\\?`));assert.equal(writes[0].options.rawBody.size,3);assert.equal(h.calls.some(x=>/cif|onboarding|loans|account/.test(x.url)),false);assert.match(h.root.textContent,/photo saved/i);h.controller.abort();assert.equal(h.root.innerHTML,'');
});

test('the all-client area search keeps its existing authority and hides photo controls without CIF review permission',async()=>{
 const h=await harness({permission:false});await h.select();assert.ok(h.root.querySelector('[data-area-client-transfer-preview-form]'));assert.equal(h.root.querySelector('[data-open-client-photo]'),null);assert.equal(h.calls.some(x=>x.url.includes('/photo')),false);h.handle.dispose();
});

test('area filtering and transfer preview preserve the mounted photo draft while canceled client navigation keeps its identity',async()=>{
 const h=await harness();await h.open();h.choose();const img=h.root.querySelector('img'),url=img.getAttribute('src');const search=h.root.querySelector('[data-area-search]');search.matches=value=>value==='[data-area-search]';search.value='One';await h.dispatch('input',search);assert.equal(h.root.querySelector('img'),img);await h.submit('[data-area-client-transfer-preview-form]',{target_area_id:'two'});assert.equal(h.root.querySelector('img'),img);assert.ok(h.root.querySelector('[data-area-client-transfer-confirm]'));
 await h.click(`[data-area-client-id="${OTHER}"]`);assert.equal(h.root.querySelector('img'),img);await h.click('[data-area-action="rename"]');assert.equal(h.root.querySelector('img'),img);await h.submit('[data-area-client-search-form]',{q:'Other'});assert.equal(h.root.querySelector('img'),img);
 h.discard=true;await h.click(`[data-area-client-id="${OTHER}"]`);assert.equal(h.root.querySelector('img'),null);await assert.rejects(fetch(url));h.handle.dispose();
});

test('unconfirmed photo blocks area operations and client changes until the original upload is resolved',async()=>{
 const h=await harness({writeError:Error('connection lost')});await h.open();await h.submit('[data-area-client-transfer-preview-form]',{target_area_id:'two'});h.choose();fire(h.root.querySelector('[data-photo-save]'),'click');await flush();assert.equal(h.handle.isWritePending(),true);const count=h.calls.length;h.discard=true;
 await h.click('[data-area-client-transfer-confirm]');await h.click('[data-area-action="rename"]');await h.click(`[data-area-client-id="${OTHER}"]`);await h.submit('[data-area-client-search-form]',{q:'Other'});await h.handle.refresh();assert.equal(h.calls.length,count);assert.ok(h.root.querySelector('[data-photo-retry]'));assert.match(h.root.querySelector('[data-area-client-photo]').textContent,/Legacy Unfinanced Client/);h.controller.abort();assert.equal(h.handle.isWritePending(),false);assert.equal(h.root.innerHTML,'');
});

test('a pending area operation prevents starting a photo upload without losing its preview',async()=>{
 const h=await harness({holdArea:true});await h.open();h.choose();await h.submit('[data-area-client-transfer-preview-form]',{target_area_id:'two'});fire(h.root.querySelector('[data-photo-save]'),'click');await flush();assert.equal(h.calls.some(x=>x.options.method==='POST'),false);assert.ok(h.root.querySelector('img'));assert.equal(h.root.querySelector('[data-photo-retry]'),null);h.resolveArea();await flush();fire(h.root.querySelector('[data-photo-save]'),'click');await flush();assert.equal(h.calls.filter(x=>x.options.method==='POST').length,1);h.handle.dispose();
});
