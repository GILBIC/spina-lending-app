import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountManagementPortfolio} from '../assets/management-portfolio.js';

const CLIENT='11111111-1111-4111-8111-111111111111',OTHER='22222222-2222-4222-8222-222222222222',PHOTO='33333333-3333-4333-8333-333333333333';
const row=(client_id,loan_id)=>({client_id,loan_id,client_name:client_id===CLIENT?'Legacy Client':'Other Client',loan_number:loan_id,principal:'100.00',remaining_balance:'50.00'});
const metadata=(photo=null)=>({client_id:CLIENT,can_upload:true,photo});
const saved={photo_id:PHOTO,version:1,content_type:'image/jpeg',byte_size:3,uploaded_at:'2026-10-10T00:00:00Z',uploaded_by_user_id:OTHER,content_url:`/api/v1/clients/${CLIENT}/photo/content?photo_id=${PHOTO}`};
const flush=async()=>{await setImmediate();await setImmediate();};
function harness({permissions=['client_onboarding.requirement.review'],writeError}={}){
 const h={root:new Element(),calls:[],discard:false,controller:new AbortController(),session:{user:{id:OTHER,role:'management'},permissions}};
 const data={summary:{},loans:[row(CLIENT,CLIENT),row(OTHER,OTHER)]};
 h.handle=mountManagementPortfolio({root:h.root,getSession:()=>h.session,signal:h.controller.signal,initialResult:{data},confirmDiscard:()=>h.discard,api:{async request(path,options={}){h.calls.push({path,options});if(options.method==='POST'){if(writeError)throw writeError;return metadata(saved);}if(path.includes('/photo/content?'))return new Blob([new Uint8Array([1,2,3])],{type:'image/jpeg'});if(path.endsWith('/photo'))return metadata();return data;}}});
 h.open=async()=>{fire(h.root.querySelector(`[data-portfolio-open="${CLIENT}"]`),'click');const button=h.root.querySelector('[data-open-client-photo]');assert.ok(button,'portfolio detail must offer photo access without any CIF or intake reference');fire(button,'click');await flush();};
 h.choose=()=>{const input=h.root.querySelector('[data-photo-file]');input.files=[new Blob([new Uint8Array([4,5,6])],{type:'image/jpeg'})];fire(input,'change');};return h;
}

test('Management can save a legacy portfolio client photo without a CIF or intake reference',async()=>{
 const h=harness();await h.open();h.choose();assert.match(h.root.querySelector('[data-portfolio-detail]').textContent,/Legacy Client/);assert.equal(h.calls.filter(x=>x.options.method==='POST').length,0);fire(h.root.querySelector('[data-photo-save]'),'click');await flush();
 const write=h.calls.find(x=>x.options.method==='POST');assert.ok(write);assert.match(write.path,new RegExp(`^/api/v1/clients/${CLIENT}/photo\\?`));assert.equal(write.options.rawBody.size,3);assert.match(h.root.querySelector('[data-portfolio-detail]').textContent,/photo saved/i);assert.equal(h.calls.some(x=>/cif|onboarding/.test(x.path)),false);h.controller.abort();assert.equal(h.root.querySelector('[data-portfolio-detail]').innerHTML,'');
});

test('portfolio photo controls remain read-only without existing CIF review permission',async()=>{
 const h=harness({permissions:[]});await h.open();assert.equal(h.root.querySelector('[data-photo-file]'),null);assert.equal(h.root.querySelector('[data-photo-save]'),null);h.handle.dispose();
});

test('canceling close, refresh or client replacement preserves a legacy client photo draft',async()=>{
 const h=harness();await h.open();h.choose();const image=h.root.querySelector('img'),url=image.getAttribute('src'),before=h.calls.length;
 fire(h.root.querySelector('[data-portfolio-close]'),'click');assert.equal(h.root.querySelector('img').getAttribute('src'),url);await h.handle.refresh();assert.equal(h.calls.length,before);assert.equal(h.root.querySelector('img').getAttribute('src'),url);fire(h.root.querySelector(`[data-portfolio-open="${OTHER}"]`),'click');assert.match(h.root.querySelector('[data-portfolio-detail]').textContent,/Legacy Client/);assert.equal(h.root.querySelector('img').getAttribute('src'),url);
 h.discard=true;fire(h.root.querySelector(`[data-portfolio-open="${OTHER}"]`),'click');assert.match(h.root.querySelector('[data-portfolio-detail]').textContent,/Other Client/);assert.equal(h.root.querySelector('img'),null);await assert.rejects(fetch(url));h.handle.dispose();
});

test('an uncertain portfolio photo blocks closing, searching and replacing the client even if discard is accepted',async()=>{
 const h=harness({writeError:Error('connection lost')});await h.open();h.choose();fire(h.root.querySelector('[data-photo-save]'),'click');await flush();assert.equal(h.handle.isWritePending(),true);h.discard=true;const before=h.calls.length;
 fire(h.root.querySelector('[data-portfolio-close]'),'click');fire(h.root.querySelector('#management-loan-search'),'submit');fire(h.root.querySelector(`[data-portfolio-open="${OTHER}"]`),'click');await h.handle.refresh();await flush();assert.equal(h.calls.length,before);assert.match(h.root.querySelector('[data-portfolio-detail]').textContent,/Legacy Client/);assert.ok(h.root.querySelector('[data-photo-retry]'));h.controller.abort();assert.equal(h.handle.isWritePending(),false);assert.equal(h.root.querySelector('[data-portfolio-detail]').innerHTML,'');
});
