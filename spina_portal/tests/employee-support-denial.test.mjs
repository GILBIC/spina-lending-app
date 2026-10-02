import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {workspace,SELF} from './helpers/employee-workspace.mjs';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';

async function mount(t){
  const root=new Element(),controller=new AbortController(),calls=[];let handle,readError=null,writeError=null,nextRead=null;
  const original=globalThis.FormData;
  globalThis.FormData=class{constructor(form){this.form=form;}get(name){return this.form.querySelector(`[name="${name}"]`)?.value;}};
  t.after(()=>{controller.abort();globalThis.FormData=original;});
  const context={root,signal:controller.signal,session:{user:{id:SELF,role:'employee'},permissions:['support.manage']},setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
    calls.push({path,options});if(path.includes('employee-operations'))return workspace();
    if(options.method){if(writeError)throw writeError;return {request:{request_id:'support-one',status:'answered',management_response:options.body.response}};}
    if(nextRead){const result=nextRead;nextRead=null;return result;}if(readError)throw readError;
    return {requests:[{request_id:'support-one',client_name:'Private synthetic client',message:'Private synthetic support message',status:'open'}]};
  }}};
  await mountEmployeeWorkspace(context);await setImmediate();
  fire(root.querySelector('[data-employee-create="leave_request"]'),'click');
  const leave=root.querySelector('[data-employee-form]'),leaveReason=leave.querySelector('[name="reason"]');leaveReason.value='Retain unrelated leave draft';
  handle.activate('employee-support');await setImmediate();
  const form=root.querySelector('.employee-support-review'),response=form.querySelector('[name="response"]'),button=form.querySelector('button');response.value='Private unsent support reply';
  return {root,context,handle,calls,leave,leaveReason,form,response,button,setReadError:error=>readError=error,setWriteError:error=>writeError=error,setNextRead:value=>nextRead=value};
}

for(const status of [401,403])test(`denied Support refresh ${status} clears its private form and keeps unrelated Employee work`,async t=>{
  const h=await mount(t);h.setReadError(Object.assign(Error('Denied synthetic support'),{status}));await h.handle.refreshVisible();
  assert.doesNotMatch(h.root.textContent,/Private synthetic support message/);assert.match(h.root.textContent,/support access.*unavailable/i);
  assert.equal(h.response.value,'');assert.equal(h.response.disabled,true);assert.equal(h.button.disabled,true);
  assert.strictEqual(h.root.querySelector('[data-employee-form]'),h.leave);assert.equal(h.leaveReason.value,'Retain unrelated leave draft');
  fire(h.form,'submit');await h.handle.refreshVisible();await setImmediate();
  assert.equal(h.calls.filter(call=>call.options.method).length,0);
  assert.equal(h.calls.filter(call=>call.path.includes('/support')).length,2);
});

for(const status of [401,403])test(`denied Support response ${status} clears values and cannot resubmit with cached grants`,async t=>{
  const h=await mount(t);h.setWriteError(Object.assign(Error('Denied synthetic response'),{status}));
  fire(h.form,'submit');await setImmediate();
  assert.doesNotMatch(h.root.textContent,/Private synthetic support message/);assert.match(h.root.textContent,/support access.*unavailable/i);
  assert.equal(h.response.value,'');assert.equal(h.response.disabled,true);assert.equal(h.button.disabled,true);
  assert.strictEqual(h.root.querySelector('[data-employee-form]'),h.leave);assert.equal(h.leaveReason.value,'Retain unrelated leave draft');
  fire(h.form,'submit');await h.handle.refreshVisible();await setImmediate();
  assert.equal(h.calls.filter(call=>call.options.method).length,1);
  assert.equal(h.calls.filter(call=>call.path.includes('/support')&&!call.options.method).length,1);
  assert.equal(h.context.employeeSupportPending,false);
});

test('transient Support read and validation failure preserve response and unrelated editor nodes',async t=>{
  const h=await mount(t);h.setReadError(Object.assign(Error('Temporary read failure'),{status:503}));await h.handle.refreshVisible();
  assert.strictEqual(h.root.querySelector('.employee-support-review'),h.form);assert.equal(h.response.value,'Private unsent support reply');assert.equal(h.button.disabled,false);
  h.setWriteError(Object.assign(Error('Response validation failed'),{status:422}));fire(h.form,'submit');await setImmediate();
  assert.strictEqual(h.root.querySelector('.employee-support-review'),h.form);assert.equal(h.response.value,'Private unsent support reply');assert.equal(h.button.disabled,false);
  assert.strictEqual(h.root.querySelector('[data-employee-form]'),h.leave);assert.equal(h.leaveReason.value,'Retain unrelated leave draft');
  assert.equal(h.calls.filter(call=>call.options.method).length,1);
});

test('a delayed queue response cannot repopulate Support after a denied save',async t=>{
  const h=await mount(t);let resolve;h.setNextRead(new Promise(done=>resolve=done));const pending=h.handle.refreshVisible();
  h.setWriteError(Object.assign(Error('Denied response'),{status:403}));fire(h.form,'submit');await setImmediate();
  resolve({requests:[{request_id:'support-late',client_name:'Late private client',message:'Late private support',status:'open'}]});await pending;
  assert.doesNotMatch(h.root.textContent,/Late private|Private synthetic support message/);assert.match(h.root.textContent,/support access.*unavailable/i);
  assert.equal(h.response.value,'');assert.equal(h.button.disabled,true);assert.equal(h.context.employeeSupportPending,false);
});

test('lost Support grant clears the response before sending any request',async t=>{
  const h=await mount(t);h.context.session={...h.context.session,permissions:[]};fire(h.form,'submit');await setImmediate();
  assert.doesNotMatch(h.root.textContent,/Private synthetic support message/);assert.equal(h.response.value,'');assert.equal(h.button.disabled,true);
  assert.strictEqual(h.root.querySelector('[data-employee-form]'),h.leave);assert.equal(h.calls.filter(call=>call.options.method).length,0);
});
