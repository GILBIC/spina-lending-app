import assert from 'node:assert/strict';
import test from 'node:test';
import {Element} from './helpers/dom.mjs';
import {mountManagementWorkspace} from '../assets/roles/management.js';
const tick=()=>new Promise(r=>setImmediate(r));

test('Today renders without secondary reads and portfolio mounts exactly once when opened',async t=>{
 const root=new Element(),calls=[];const abort=new AbortController();t.after(()=>abort.abort());let handle;
 const context={root,signal:abort.signal,session:{user:{id:'owner',role:'management'},permissions:['management.dashboard.view']},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{request(path){calls.push(path);if(path==='/api/v1/account')return Promise.resolve({profile:{full_name:'Synthetic Owner'}});if(path.includes('dashboard-overview'))return Promise.resolve({metrics:[]});if(path.includes('/management/loans'))return Promise.resolve({summary:{active_client_count:0,active_loan_count:0,active_remaining_total:'0.00',overdue_active_count:0},loans:[]});return new Promise(()=>{});}}};
 const pending=mountManagementWorkspace(context);await tick();
 assert.match(root.textContent,/Today/);assert.ok(handle,'handle registered before secondary requests can block');
 assert.deepEqual(calls.sort(),['/api/v1/account','/api/v1/management/dashboard-overview'].sort());
 await pending;await handle.activate('management-clients-loans');await handle.activate('management-overview');await handle.activate('management-clients-loans');
 assert.equal(calls.filter(x=>x.includes('/management/loans')).length,1);
 assert.equal(calls.some(x=>x.includes('loan-operations')),false);
});

test('Account read failure is local and does not remove permitted task navigation',async t=>{
 const root=new Element();const abort=new AbortController();t.after(()=>abort.abort());let handle;
 await mountManagementWorkspace({root,signal:abort.signal,session:{user:{id:'owner',role:'management'},permissions:[]},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(path){if(path==='/api/v1/account')throw new Error('Unavailable');return {summary:{},loans:[]};}}});await tick();
 assert.ok(root.querySelector('#management-clients-loans'));assert.ok(handle);assert.match(root.querySelector('#management-account').textContent,/Unavailable/);
});
