import test from 'node:test';import assert from 'node:assert/strict';import {Element} from './helpers/dom.mjs';import {mountClientWorkspace} from '../assets/roles/client.js';
const tick=()=>new Promise(r=>setTimeout(r,0));
test('updates statement and 7x7 do not block shell; revisits deduplicate actual reads',async()=>{
 const root=new Element();let handle;const calls=[];const controller=new AbortController();
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{request(path){calls.push(path);if(path==='/api/v1/account')return Promise.resolve({});if(path==='/api/v1/client/loans')return Promise.resolve({loans:[]});return new Promise(()=>{});}}};
 void mountClientWorkspace(context);await tick();assert.ok(root.querySelector('#client-support-form'));assert.equal(typeof handle?.activate,'function');assert.equal(calls.includes('/api/v1/client/statement'),false);handle.activate('client-statement');handle.activate('client-statement');assert.equal(calls.filter(x=>x==='/api/v1/client/statement').length,1);controller.abort();assert.equal(root.innerHTML,'');
});
test('header refresh preserves mounted unrelated forms',async()=>{
 const root=new Element();let handle;const context={root,setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{request:async path=>path.includes('loans')?{loans:[]}:path.includes('notifications')?[]:{}}};await mountClientWorkspace(context);await tick();const form=root.querySelector('#client-support-form');form.querySelector('[name="message"]').value='keep draft';await handle.refreshVisible();assert.equal(root.querySelector('#client-support-form'),form);assert.equal(form.querySelector('[name="message"]').value,'keep draft');handle.dispose();
});
