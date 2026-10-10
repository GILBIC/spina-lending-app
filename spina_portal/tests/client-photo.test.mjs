import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { SpinaApi } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/client-photo.js', import.meta.url);
const CLIENT = '11111111-1111-4111-8111-111111111111';
const OTHER = '22222222-2222-4222-8222-222222222222';
const PHOTO = '33333333-3333-4333-8333-333333333333';
const path = `/api/v1/clients/${CLIENT}/photo`;
const photo = {photo_id:PHOTO,version:1,content_type:'image/jpeg',byte_size:3,uploaded_at:'2026-10-10T00:00:00Z',uploaded_by_user_id:OTHER,content_url:`${path}/content?photo_id=${PHOTO}`};
const metadata = (value=null,canUpload=true) => ({client_id:CLIENT,can_upload:canUpload,photo:value});
const response = value => new Response(JSON.stringify({success:true,data:value}),{headers:{'content-type':'application/json'}});
const deferred = () => {let resolve;const promise=new Promise(r=>resolve=r);return {resolve,promise};};
async function harness({role='employee',permissions=['client_onboarding.requirement.review'],route,initial=metadata(),getClientId}={}) {
  assert.equal(existsSync(moduleUrl),true,'Client photo panel is not implemented');
  const {mountClientPhoto,mountClientPhotoLauncher}=await import(moduleUrl.href);
  const h={root:new Element(),calls:[],urls:[],revoked:[],session:{user:{id:OTHER,role,roles:[role]},permissions,access_token:'photo-token'},controller:new AbortController()};
  h.api=new SpinaApi({sessionStore:{load:()=>h.session,deviceId:()=> 'photo-device',clear(){h.session=null;}},fetchImpl:async(url,options)=>{h.calls.push({url,...options});return route?route(url,options):url.includes('/content?')?new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}}):response(initial);}});
  h.options={root:h.root,api:h.api,getSession:()=>h.session,clientId:CLIENT,clientName:'Synthetic Client',allowUpload:true,signal:h.controller.signal,getClientId,urlApi:{createObjectURL(blob){const url=`blob:photo-${h.urls.length+1}`;h.urls.push({blob,url});return url;},revokeObjectURL(url){h.revoked.push(url);}}};
  h.mount=()=>h.handle=mountClientPhoto(h.options);
  h.launch=()=>h.handle=mountClientPhotoLauncher(h.options);
  return h;
}
async function choose(h,file=new Blob([new Uint8Array([4,5,6])],{type:'image/jpeg'}),selector='[data-photo-file]') {const input=h.root.querySelector(selector);input.files=[file];fire(input,'change');await setImmediate();return file;}
async function click(h,selector) {fire(h.root.querySelector(selector),'click');await setImmediate();}

test('missing photo offers an optional preview beside the client name and an authenticated exact-byte save',async()=>{
  const h=await harness({route:(url,options)=>response(options.method==='POST'?metadata(photo):metadata())});h.mount();await h.handle.ready;
  assert.match(h.root.textContent,/No photo/);assert.match(h.root.textContent,/Synthetic Client/);
  assert.equal(h.root.querySelector('[data-photo-camera]').getAttribute('capture'),'user');
  const file=await choose(h);assert.equal(h.root.querySelector('img').getAttribute('src'),'blob:photo-1');
  assert.equal(h.calls.filter(x=>x.method==='POST').length,0);
  await click(h,'[data-photo-save]');
  const write=h.calls.find(x=>x.method==='POST');assert.ok(write);assert.equal(write.body,file);
  assert.match(write.url,new RegExp(`^${path}\\?request_id=[0-9a-f-]+&expected_version=0$`));
  assert.equal(write.headers.Authorization,'Bearer photo-token');assert.equal(write.headers['X-Device-Id'],'photo-device');assert.equal(write.headers['Content-Type'],'image/jpeg');assert.equal(write.cache,'no-store');
  assert.equal(h.handle.isDirty(),false);h.handle();assert.ok(h.revoked.includes('blob:photo-1'));
});

test('private current photo uses authenticated bytes and cannot grant upload from metadata alone',async()=>{
  const h=await harness({role:'collector',initial:metadata(photo,true)});h.mount();await h.handle.ready;
  assert.equal(h.root.querySelector('[data-photo-file]'),null);assert.equal(h.root.querySelector('[data-photo-save]'),null);
  assert.equal(h.calls[1].url,photo.content_url);assert.equal(h.calls[1].headers.Authorization,'Bearer photo-token');assert.equal(h.calls[1].cache,'no-store');
  assert.equal(h.root.querySelector('img').getAttribute('src'),'blob:photo-1');h.controller.abort();assert.deepEqual(h.revoked,['blob:photo-1']);assert.equal(h.root.innerHTML,'');
});

test('server upload denial keeps an office photo read-only',async()=>{
  const h=await harness({initial:metadata(null,false)});h.mount();await h.handle.ready;assert.equal(h.root.querySelector('[data-photo-file]'),null);assert.equal(h.root.querySelector('[data-photo-save]'),null);h.handle();
});

test('an uncertain upload retains the exact image, version and request ID until explicit retry succeeds',async()=>{
  let writes=0;const h=await harness({route:(url,options)=>{if(options.method==='POST'){if(++writes===1)throw Error('connection lost');return response(metadata(photo));}return url.includes('/content?')?new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}}):response(metadata());}});h.mount();await h.handle.ready;
  const file=await choose(h);await click(h,'[data-photo-save]');assert.equal(h.handle.isUncertain(),true);assert.equal(writes,1);
  assert.equal(h.root.querySelector('[data-photo-file]').disabled,true);assert.equal(h.root.querySelector('[data-photo-camera]').disabled,true);
  const retry=h.root.querySelector('[data-photo-retry]');assert.ok(retry);await choose(h,new Blob(['other'],{type:'image/png'}));await click(h,'[data-photo-retry]');
  const uploads=h.calls.filter(x=>x.method==='POST');assert.equal(uploads.length,2);assert.equal(uploads[0].url,uploads[1].url);assert.equal(uploads[1].body,file);assert.equal(h.handle.isUncertain(),false);h.handle();
});

test('invalid local file never replaces the existing preview or sends bytes',async()=>{
  const h=await harness();h.mount();await h.handle.ready;await choose(h);await choose(h,new Blob(['pdf'],{type:'application/pdf'}));assert.equal(h.root.querySelector('img').getAttribute('src'),'blob:photo-1');assert.match(h.root.textContent,/JPEG or PNG/);assert.equal(h.calls.length,1);h.handle();
});

test('late bytes are suppressed when the selected client or session changes',async()=>{
  for(const change of ['client','session','abort']){
    const waiting=deferred();let selected=CLIENT;const h=await harness({getClientId:()=>selected,route:(url)=>url.includes('/content?')?waiting.promise:response(metadata(photo))});h.mount();await setImmediate();
    if(change==='client')selected=OTHER;else if(change==='session')h.session={...h.session,user:{...h.session.user,id:CLIENT}};else h.controller.abort();
    waiting.resolve(new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}}));await h.handle.ready;assert.equal(h.root.innerHTML,'');assert.deepEqual(h.urls,[]);
  }
});

test('metadata cannot direct authenticated photo requests to another client or URL',async()=>{
  for(const content_url of [`/api/v1/clients/${OTHER}/photo/content?photo_id=${PHOTO}`,'https://external.example/photo']){
    const h=await harness({initial:metadata({...photo,content_url})});h.mount();await h.handle.ready;assert.equal(h.calls.length,1);assert.equal(h.root.querySelector('img'),null);h.handle();
  }
});

test('launcher opens the selected photo only on request and cleans the draft on disposal',async()=>{
  const h=await harness();h.launch();assert.equal(h.calls.length,0);await click(h,'[data-open-client-photo]');await choose(h);assert.equal(h.handle.isDirty(),true);h.handle();assert.equal(h.root.innerHTML,'');assert.deepEqual(h.revoked,['blob:photo-1']);
});

test('a launcher retained after a session switch cannot open an old client record',async()=>{
  const h=await harness();h.launch();h.session={...h.session,user:{...h.session.user,id:CLIENT}};await click(h,'[data-open-client-photo]');assert.equal(h.calls.length,0);assert.equal(h.root.innerHTML,'');
});

test('successful exact retry can show a newer current photo without claiming it is the original image',async()=>{
  const h=await harness({route:(url,options)=>url.includes('/content?')?new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}}):response(options.method==='POST'?metadata({...photo,version:3}):metadata())});h.mount();await h.handle.ready;await choose(h);await click(h,'[data-photo-save]');assert.equal(h.handle.isUncertain(),false);assert.equal(h.handle.isDirty(),false);assert.match(h.root.textContent,/newer client photo/);assert.equal(h.calls.at(-1).url,photo.content_url);h.handle();
});

test('a stale version keeps the preview but requires a fresh metadata read before another save',async()=>{
  let writes=0,reads=0;const h=await harness({route:(url,options)=>{if(url.includes('/content?'))return new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}});if(options.method==='POST'){if(++writes===1)return new Response(JSON.stringify({detail:'stale version'}),{status:409,headers:{'content-type':'application/json'}});return response(metadata({...photo,version:2}));}return response(metadata(++reads===1?null:photo));}});h.mount();await h.handle.ready;const file=await choose(h);await click(h,'[data-photo-save]');assert.equal(h.handle.isUncertain(),false);assert.equal(h.handle.isDirty(),true);assert.equal(h.root.querySelector('[data-photo-save]'),null);assert.equal(writes,1);await click(h,'[data-photo-reload]');await click(h,'[data-photo-save]');const uploads=h.calls.filter(x=>x.method==='POST');assert.equal(uploads[1].body,file);assert.notEqual(uploads[1].url,uploads[0].url);assert.match(uploads[1].url,/expected_version=1$/);assert.equal(h.handle.isDirty(),false);h.handle();
});

test('a file over 5 MiB is refused before any preview URL or upload exists',async()=>{
  const h=await harness();h.mount();await h.handle.ready;await choose(h,new Blob([new Uint8Array(5*1024*1024+1)],{type:'image/jpeg'}));assert.equal(h.handle.isDirty(),false);assert.deepEqual(h.urls,[]);assert.equal(h.calls.length,1);h.handle();
});

const deniedResponse=status=>new Response(JSON.stringify({detail:'Private failure detail must not be rendered'}),{status,headers:{'content-type':'application/json'}});

for(const boundary of ['metadata','content','upload'])test(`forced upgrade during ${boundary} clears private photo state and write authority`,async()=>{
  let deny=false;
  const h=await harness({route:(url,options)=>{
    if(deny && ((boundary==='metadata' && url===path) || (boundary==='content' && url.includes('/content?')) || (boundary==='upload' && options.method==='POST')))return deniedResponse(426);
    if(url.includes('/content?'))return new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}});
    return response(metadata(photo));
  }});h.mount();await h.handle.ready;await choose(h);const detachedSave=h.root.querySelector('[data-photo-save]');deny=true;
  await click(h,boundary==='upload'?'[data-photo-save]':'[data-photo-reload]');
  assert.doesNotMatch(h.root.textContent,/Synthetic Client|Private failure/);assert.match(h.root.textContent,/unavailable/i);assert.equal(h.root.querySelector('img'),null);assert.equal(h.root.querySelector('[data-photo-file]'),null);assert.equal(h.root.querySelector('[data-photo-retry]'),null);assert.equal(h.handle.isDirty(),false);assert.equal(h.handle.isUncertain(),false);assert.ok(h.revoked.includes('blob:photo-1'));assert.ok(h.revoked.includes('blob:photo-2'));
  const count=h.calls.length;fire(detachedSave,'click');await setImmediate();assert.equal(h.calls.length,count);h.handle();
});

test('a replaced photo content 404 leaves a visible reload that reauthorizes metadata before showing the current image',async()=>{
  let bytes=0,reads=0;
  const h=await harness({route:url=>{if(url.includes('/content?'))return ++bytes===1?deniedResponse(404):new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'image/jpeg'}});reads++;return response(metadata(photo));}});h.launch();await click(h,'[data-open-client-photo]');
  assert.equal(h.root.querySelector('img'),null);assert.equal(h.root.querySelector('[data-photo-file]'),null);const reload=h.root.querySelector('[data-photo-reload]');assert.ok(reload);assert.equal(reload.disabled,false);assert.match(h.root.textContent,/Reload/);assert.equal(reads,1);
  await click(h,'[data-photo-reload]');assert.equal(reads,2);assert.equal(h.root.querySelector('img').getAttribute('src'),'blob:photo-1');assert.ok(h.root.querySelector('[data-photo-file]'));h.handle();
});

test('metadata denial after a replaced photo clears a retained draft and shows a generic unavailable message',async()=>{
  let phase='initial';
  const h=await harness({route:url=>{if(url.includes('/content?'))return deniedResponse(404);if(phase==='denied')return deniedResponse(404);return response(metadata(phase==='initial'?null:photo));}});h.mount();await h.handle.ready;await choose(h);phase='replaced';await click(h,'[data-photo-reload]');assert.equal(h.handle.isDirty(),true);assert.equal(h.root.querySelector('[data-photo-save]'),null);phase='denied';await click(h,'[data-photo-reload]');
  assert.doesNotMatch(h.root.textContent,/Synthetic Client|Private failure/);assert.match(h.root.textContent,/unavailable/i);assert.equal(h.root.querySelector('img'),null);assert.equal(h.handle.isDirty(),false);assert.deepEqual(h.revoked,['blob:photo-1']);h.handle();
});

test('a confirmed upload whose current content is replaced stays saved and offers metadata reload without another upload',async()=>{
  const h=await harness({route:(url,options)=>url.includes('/content?')?deniedResponse(404):response(options.method==='POST'?metadata(photo):metadata())});h.mount();await h.handle.ready;await choose(h);await click(h,'[data-photo-save]');
  assert.equal(h.handle.isDirty(),false);assert.equal(h.handle.isUncertain(),false);assert.match(h.root.textContent,/saved/i);assert.ok(h.root.querySelector('[data-photo-reload]'));assert.equal(h.root.querySelector('[data-photo-file]'),null);assert.equal(h.calls.filter(x=>x.method==='POST').length,1);h.handle();
});
