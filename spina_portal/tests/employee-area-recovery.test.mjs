import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {workspace, SELF} from './helpers/employee-workspace.mjs';
import {mountAreaManagement} from '../assets/area-management.js';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';

const areas = name => ({areas:[{area_id:'area-one', parent_area_id:null, name, full_path:name,
  depth:0, sort_order:0, is_active:true, is_legacy_unmapped:false, explicit_collector:null,
  effective_collector:null, direct_client_count:0, subtree_client_count:0, child_count:0}]});
const session = () => ({user:{id:SELF,role:'employee'},permissions:['area.manage']});
const deferred = () => {let resolve; const promise=new Promise(done=>resolve=done); return {promise,resolve};};
function dispatch(root, type, target) {
  const event=new Event(type,{cancelable:true});
  Object.defineProperty(event,'target',{value:target});
  root.dispatchEvent(event);
}
function rename(root) {
  dispatch(root,'click',root.querySelector('[data-area-action="rename"]'));
  const form=root.querySelector('[data-area-editor]');
  assert.ok(form,'the actual Area rename action opens its editor');
  const input=form.querySelector('[name="name"]');
  form.matches=selector=>selector==='[data-area-editor]';
  form.elements={name:input};
  input.value='Unsent synthetic Area name';
  return {form,input};
}

test('a failed initial Area read has a local retry and concurrent retries share one read',async t=>{
  const root=new Element(),controller=new AbortController(),next=deferred();let reads=0;
  t.after(()=>controller.abort());
  await mountAreaManagement({root,signal:controller.signal,session:session(),api:{request(){
    reads++;return reads===1?Promise.reject(Error('Synthetic temporary Area failure')):next.promise;
  }}});
  const retry=root.querySelector('[data-area-retry]');
  assert.ok(retry,'the failure has an actionable local Retry');
  fire(retry,'click');fire(retry,'click');
  assert.equal(reads,2);
  next.resolve(areas('Recovered Area'));await setImmediate();
  assert.match(root.textContent,/Recovered Area/);
  fire(retry,'click');await setImmediate();
  assert.equal(reads,2,'a detached old Retry cannot remount the successful editor');
});

test('Employee header recovers a failed Area read, then refresh and revisit retain its exact editor',async t=>{
  const root=new Element(),controller=new AbortController(),calls=[];let handle,areaReads=0;
  t.after(()=>controller.abort());
  await mountEmployeeWorkspace({root,signal:controller.signal,session:session(),setNavigation(){},
    registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
      calls.push({path,options});
      if(path.includes('employee-operations'))return workspace();
      if(!options.method&&++areaReads===1)throw Error('Synthetic initial Area failure');
      return areas('Current Area');
    }}});
  await setImmediate();
  assert.equal(calls.filter(call=>call.path.includes('/areas')).length,0);
  handle.activate('employee-area-management');handle.activate('employee-area-management');await setImmediate();
  assert.equal(areaReads,1);
  await handle.refreshVisible();await setImmediate();
  assert.equal(areaReads,2,'header Refresh retries the failed mount');
  const target=root.querySelector('#employee-area-management'),{form,input}=rename(target);
  await handle.refreshVisible();
  handle.activate('employee-operations');handle.activate('employee-area-management');await setImmediate();
  assert.strictEqual(target.querySelector('[data-area-editor]'),form);
  assert.equal(input.value,'Unsent synthetic Area name');
  assert.equal(areaReads,2,'routine refresh does not recreate a successful Area mount');
  dispatch(target,'submit',form);await setImmediate();
  assert.equal(calls.filter(call=>call.options.method).length,1,'revisit does not bind a duplicate save');
  assert.equal(calls.filter(call=>call.path.includes('employee-operations')).length,1);
});

test('aborting an initial Area read rejects its late result without touching a newer surface',async()=>{
  const root=new Element(),controller=new AbortController(),read=deferred();let options;
  const mounting=mountAreaManagement({root,signal:controller.signal,session:session(),api:{request(_path,value){options=value;return read.promise;}}});
  controller.abort();root.innerHTML='<p>New workspace surface</p>';
  read.resolve(areas('Old private Area'));await mounting;
  assert.equal(root.textContent,'New workspace surface');
  assert.equal(options.signal.aborted,true,'the owned request is aborted as well as its rendering');
});

test('a newer Area mount owns the root when an older initial read finishes later',async t=>{
  const root=new Element(),old=deferred(),controller=new AbortController();let oldReads=0;
  t.after(()=>controller.abort());
  const mounting=mountAreaManagement({root,signal:controller.signal,session:session(),api:{request(){oldReads++;return old.promise;}}});
  await mountAreaManagement({root,signal:controller.signal,session:session(),api:{request:async()=>areas('New current Area')}});
  old.resolve(areas('Old private Area'));const oldHandle=await mounting;
  assert.match(root.textContent,/New current Area/);assert.doesNotMatch(root.textContent,/Old private Area/);
  await oldHandle.refreshReadOnly();assert.equal(oldReads,1);
});

for(const changed of ['identity','Area grant'])test(`a changed ${changed} rejects a late Area read through the live session getter`,async()=>{
  const root=new Element(),read=deferred();let current=session();
  const mounting=mountAreaManagement({root,session:current,getSession:()=>current,api:{request:()=>read.promise}});
  current=changed==='identity'?{...current,user:{id:'different-user'}}:{...current,permissions:[]};
  read.resolve(areas('Old private Area'));const handle=await mounting;
  assert.equal(root.innerHTML,'');await handle.refreshReadOnly();assert.equal(root.innerHTML,'');
});

test('Area disposal clears a retained draft and leaves old delegated save handlers inert',async()=>{
  const root=new Element(),calls=[];
  const handle=await mountAreaManagement({root,session:session(),api:{async request(path,options={}){calls.push({path,options});return areas('Current Area');}}});
  const {form,input}=rename(root),button=form.querySelector('button');
  handle.dispose();
  assert.equal(input.value,'');assert.equal(input.disabled,true);assert.equal(button.disabled,true);assert.equal(root.innerHTML,'');
  dispatch(root,'submit',form);await setImmediate();
  assert.equal(calls.filter(call=>call.options.method).length,0);
});

test('a late Area save after abort cannot reload records or repaint another workspace',async()=>{
  const root=new Element(),controller=new AbortController(),write=deferred(),calls=[];
  await mountAreaManagement({root,signal:controller.signal,session:session(),api:{request(path,options={}){
    calls.push({path,options});return options.method?write.promise:Promise.resolve(areas('Current Area'));
  }}});
  const {form}=rename(root);dispatch(root,'submit',form);await setImmediate();
  controller.abort();root.innerHTML='<p>New workspace surface</p>';write.resolve({});await setImmediate();
  assert.equal(root.textContent,'New workspace surface');
  assert.equal(calls.length,2,'late accepted save does not start an old-scope reload');
});

const collectorChoices={collectors:[{user_id:'collector-one',full_name:'Synthetic Collector',username:'synthetic-collector'}]};
async function partialArea(t,readChoices){
  const root=new Element(),controller=new AbortController(),calls=[];let handle,choiceReads=0;
  t.after(()=>controller.abort());
  await mountEmployeeWorkspace({root,signal:controller.signal,
    session:{...session(),permissions:['area.manage','area.collector.assign']},setNavigation(){},
    registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
      calls.push({path,options});
      if(path.includes('employee-operations'))return workspace();
      if(path.endsWith('/collectors'))return readChoices(++choiceReads);
      assert.equal(path,'/api/v1/areas');
      return areas('Current Area');
    }}});
  handle.activate('employee-area-management');await setImmediate();
  return {root:root.querySelector('#employee-area-management'),handle,controller,calls};
}
function unavailable(){throw Object.assign(Error('Synthetic choices unavailable'),{status:503});}

test('local Collector choices retry preserves the Area draft and shares its read with header Refresh',async t=>{
  const next=deferred(),{root,handle,calls}=await partialArea(t,count=>count===1?unavailable():next.promise);
  const {form,input}=rename(root),areaRow=root.querySelector('[data-area-id]');
  const retry=root.querySelector('[data-area-collectors-retry]');
  assert.ok(retry,'a partial choices failure offers a local Retry');
  dispatch(root,'click',retry);const refresh=handle.refreshVisible();await setImmediate();
  assert.equal(calls.filter(call=>call.path.endsWith('/collectors')).length,2);
  assert.strictEqual(root.querySelector('[data-area-editor]'),form);
  next.resolve(collectorChoices);await refresh;await setImmediate();
  assert.strictEqual(root.querySelector('[data-area-editor]'),form);
  assert.strictEqual(root.querySelector('[data-area-id]'),areaRow);
  assert.equal(input.value,'Unsent synthetic Area name');
  assert.equal(root.querySelector('[data-area-collectors-retry]'),null);
  assert.equal(calls.filter(call=>call.path==='/api/v1/areas').length,1);
  assert.equal(calls.filter(call=>call.options.method).length,0);
  dispatch(root,'click',root.querySelector('[data-area-action="collector"]'));
  assert.match(root.querySelector('[data-area-collector-select]').textContent,/Synthetic Collector/);
});

test('header Refresh recovers choices in the current Collector form without replacing its select or selecting a person',async t=>{
  const next=deferred(),{root,handle,calls}=await partialArea(t,count=>count===1?unavailable():next.promise);
  const refresh=handle.refreshVisible();await setImmediate();
  assert.equal(calls.filter(call=>call.path.endsWith('/collectors')).length,2,'header Refresh retries the failed choices read');
  dispatch(root,'click',root.querySelector('[data-area-action="collector"]'));
  const form=root.querySelector('[data-area-collector-editor]'),select=form.querySelector('[data-area-collector-select]');
  next.resolve(collectorChoices);await refresh;
  assert.strictEqual(root.querySelector('[data-area-collector-editor]'),form);
  assert.strictEqual(root.querySelector('[data-area-collector-select]'),select);
  assert.match(select.textContent,/Synthetic Collector/);
  assert.equal(select.value,'','recovery does not choose a Collector for the owner');
  assert.equal(calls.filter(call=>call.options.method).length,0);
});

test('another failed choices retry keeps the Area draft and permits a later local recovery',async t=>{
  const {root,handle,calls}=await partialArea(t,count=>count<3?unavailable():collectorChoices);
  const {form,input}=rename(root);
  await handle.refreshVisible();
  assert.equal(calls.filter(call=>call.path.endsWith('/collectors')).length,2);
  assert.strictEqual(root.querySelector('[data-area-editor]'),form);
  const retry=root.querySelector('[data-area-collectors-retry]');
  assert.ok(retry);assert.equal(retry.disabled,false);
  dispatch(root,'click',retry);await setImmediate();
  assert.strictEqual(root.querySelector('[data-area-editor]'),form);
  assert.equal(input.value,'Unsent synthetic Area name');
  assert.equal(root.querySelector('[data-area-collectors-retry]'),null);
  assert.equal(calls.filter(call=>call.path==='/api/v1/areas').length,1);
});

test('a denied choices retry clears the retained Area draft and never retries the denied mount',async t=>{
  const {root,handle,calls}=await partialArea(t,count=>{
    if(count===1)return unavailable();
    throw Object.assign(Error('Synthetic denial'),{status:403});
  });
  const {input}=rename(root);await handle.refreshVisible();
  assert.equal(calls.filter(call=>call.path.endsWith('/collectors')).length,2);
  assert.equal(input.value,'');assert.equal(input.disabled,true);
  assert.match(root.textContent,/Area access is unavailable/);
  await handle.refreshVisible();
  assert.equal(calls.filter(call=>call.path.endsWith('/collectors')).length,2);
});
