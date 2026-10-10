import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountOfficeCifSelection} from '../assets/office-cif-selection.js';
import {mountCollectorRouteView} from '../assets/collector-route-view.js';
import {mountClientWorkspace} from '../assets/roles/client.js';

const CLIENT='11111111-1111-4111-8111-111111111111',OTHER='22222222-2222-4222-8222-222222222222';
const flush=async()=>{await setImmediate();await setImmediate();};
const meta=(id=CLIENT)=>({client_id:id,can_upload:true,photo:null});
const photoPath=`/api/v1/clients/${CLIENT}/photo`;
const session={user:{id:OTHER,role:'employee',roles:['employee']},permissions:['client_onboarding.requirement.review']};

test('office selected CIF offers photo upload separately and keeps its uncertain operation when another case is requested',async()=>{
 const root=new Element(),calls=[];let handle;
 const dispose=mountOfficeCifSelection({root,session,getSession:()=>session,registerHandle:h=>handle=h,confirmDiscard:()=>true,api:{async request(path,options={}){calls.push({path,options});if(options.method==='POST')throw Error('connection lost');if(path.endsWith('/photo'))return meta();if(path.endsWith('/cif-client'))return {client_id:CLIENT,application_reference:'APP-1'};return {client_id:CLIENT,cif_version_id:OTHER,version_number:1,status:'draft',liveness_status:'pending',review_scope:'cif_information_only',full_name:'Office Selected Client',phone_number:'09170000000',present_address:'Synthetic address',email:null};}}});
 await handle.openCase('APP-1');const launcher=root.querySelector('[data-open-client-photo]');assert.ok(launcher,'selected CIF must offer its own photo control');fire(launcher,'click');await flush();
 const input=root.querySelector('[data-photo-file]');input.files=[new Blob(['jpeg'],{type:'image/jpeg'})];fire(input,'change');fire(root.querySelector('[data-photo-save]'),'click');await flush();
 assert.equal(handle.isUncertain(),true);const prior=calls.length;await handle.openCase('APP-2');assert.equal(calls.length,prior);assert.match(root.textContent,/Office Selected Client/);
 assert.equal(calls.filter(x=>x.options.method==='POST').length,1);assert.match(calls.find(x=>x.options.method==='POST').path,/\/photo\?/);dispose();assert.equal(root.innerHTML,'');
});

test('collector photo opens only for a current route entry and disappears when that assignment leaves the route',async()=>{
 const root=new Element(),attention=new Element(),calls=[];let route={route_date:'2026-10-10',entries:[{route_entry_id:'route-1',client_id:CLIENT,client_name:'Route Client',loan_id:OTHER,area:'One',loan_type:'Regular',daily_amount:'1.00'}]};
 const handle=mountCollectorRouteView({routeRoot:root,attentionRoot:attention,getSession:()=>({user:{role:'collector'},permissions:['route.view']}),getRoute:()=>route,guard:{current:true,sync(){}},api:{async request(path){calls.push(path);return meta();}}});handle.applyRoute(route);
 const button=root.querySelector('[data-view-client-photo]');assert.ok(button,'assigned route entry must offer a photo view');fire(button,'click');await flush();assert.deepEqual(calls,[photoPath]);assert.match(root.textContent,/Route Client/);assert.equal(root.querySelector('[data-photo-file]'),null);
 route={...route,entries:[]};handle.applyRoute(route);assert.equal(root.querySelector('[data-route-photo]').innerHTML,'');fire(button,'click');await flush();assert.deepEqual(calls,[photoPath]);handle.dispose();
});

test('client account uses only its returned linked client identity and never exposes upload',async()=>{
 const root=new Element(),controller=new AbortController(),calls=[];let handle;const own={user:{id:OTHER,role:'client',client_id:CLIENT},permissions:[]};
 await mountClientWorkspace({root,signal:controller.signal,session:own,getSession:()=>own,setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{async request(path){calls.push(path);if(path==='/api/v1/client/loans')return {client:{client_id:CLIENT,client_name:'Own Client'},loans:[]};if(path===photoPath)return meta();if(path==='/api/v1/activity-notifications')return [];return {profile:{full_name:'Own Client'}};}}});await flush();await handle.activate('client-account');
 const launcher=root.querySelector('#client-account').querySelector('[data-open-client-photo]');assert.ok(launcher,'linked client account must expose its own photo');fire(launcher,'click');await flush();assert.equal(calls.filter(p=>p===photoPath).length,1);assert.equal(root.querySelector('[data-photo-file]'),null);controller.abort();assert.equal(root.innerHTML,'');
});

test('an eligible selected client can add a photo before the first CIF is begun',async()=>{
 const root=new Element(),calls=[];let handle;
 const saved={photo_id:OTHER,version:1,content_type:'image/jpeg',byte_size:3,uploaded_at:'2026-10-10T00:00:00Z',uploaded_by_user_id:OTHER,content_url:`${photoPath}/content?photo_id=${OTHER}`};
 const dispose=mountOfficeCifSelection({root,session,getSession:()=>session,registerHandle:h=>handle=h,api:{async request(path,options={}){calls.push({path,options});if(path.endsWith('/cif-client'))return {client_id:CLIENT,application_reference:'INTAKE-NO-CIF'};if(path.endsWith('/cif/review-summary'))throw Object.assign(Error('No CIF yet'),{status:404});if(options.method==='POST')return {...meta(),photo:saved};if(path.includes('/photo/content?'))return new Blob([new Uint8Array([1,2,3])],{type:'image/jpeg'});return meta();}}});
 await handle.openCase('INTAKE-NO-CIF');assert.ok(root.querySelector('[data-begin-cif]'));fire(root.querySelector('[data-open-client-photo]'),'click');await flush();const input=root.querySelector('[data-photo-file]');assert.ok(input);input.files=[new Blob([new Uint8Array([4,5,6])],{type:'image/jpeg'})];fire(input,'change');fire(root.querySelector('[data-photo-save]'),'click');await flush();
 assert.match(root.textContent,/photo saved/i);assert.ok(root.querySelector('[data-begin-cif]'),'photo upload does not create or complete a CIF');const writes=calls.filter(x=>x.options.method==='POST');assert.equal(writes.length,1);assert.match(writes[0].path,/\/photo\?/);dispose();
});
