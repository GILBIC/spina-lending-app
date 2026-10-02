import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
import {mountManagementWorkspace} from '../assets/roles/management.js';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const actor='10000000-0000-4000-8000-000000000001';

test('Management recipient history mounts lazily for view-only authority without receive controls',async t=>{
 const root=new Element(),calls=[],abort=new AbortController();t.after(()=>abort.abort());let handle;
 await mountManagementWorkspace({root,signal:abort.signal,session:{user:{id:actor,role:'management'},permissions:['remittance.view']},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(path){calls.push(path);if(path==='/api/v1/notifications')return [];return {profile:{}};}}});
 assert.equal(calls.includes('/api/v1/notifications'),false);assert.ok(root.querySelector('#management-remittances'));
 assert.equal(await handle.activate('management-collections','management-remittances'),true);await tick();assert.equal(calls.filter(p=>p==='/api/v1/notifications').length,1);
 assert.match(root.querySelector('#management-remittances').textContent,/remittance/i);assert.equal(root.querySelector('[data-remittance-accept]'),null);
 await handle.activate('management-overview');await handle.activate('management-collections','management-remittances');assert.equal(calls.filter(p=>p==='/api/v1/notifications').length,1);
});

test('failed receiver list retains a local read retry and never claims an empty queue',async t=>{
 const root=new Element(),abort=new AbortController();t.after(()=>abort.abort());let handle,fail=true,reads=0;
 await mountManagementWorkspace({root,signal:abort.signal,session:{user:{id:actor,role:'management'},permissions:['remittance.view','remittance.receive']},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(path){if(path==='/api/v1/notifications'){reads++;if(fail)throw Error('Synthetic unavailable');return [];}return {profile:{}};}}});
 await handle.activate('management-collections','management-remittances');await tick();const task=root.querySelector('#management-remittances');assert.ok(task);assert.match(task.textContent,/could not refresh|not loaded/i);assert.doesNotMatch(task.textContent,/No remittance notification/);
 fail=false;fire(task.querySelector('[data-remittance-retry]'),'click');await tick();assert.equal(reads,2);assert.match(task.textContent,/No remittance notification/);
});

test('receiving permission alone does not fabricate remittance viewing authority',async t=>{
 const root=new Element(),abort=new AbortController();t.after(()=>abort.abort());let handle;
 await mountManagementWorkspace({root,signal:abort.signal,session:{user:{id:actor,role:'management'},permissions:['remittance.receive']},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(){return {};}}});
 assert.equal(root.querySelector('#management-remittances'),null);assert.equal(await handle.activate('management-collections','management-remittances'),false);
});
