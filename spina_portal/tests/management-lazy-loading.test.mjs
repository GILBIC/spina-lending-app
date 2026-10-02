import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
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

test('mounted report refresh retains its filters and initial collection tabs work',async t=>{
 const root=new Element(),calls=[],abort=new AbortController();t.after(()=>abort.abort());let handle;
 const context={root,signal:abort.signal,session:{user:{id:'owner',role:'management'},permissions:['management.dashboard.view']},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(path){calls.push(path);if(path.includes('loan-operations'))return {summary:{},entries:[],audits:[]};if(path.includes('past-due'))return {summary:{},rows:[]};return {profile:{},metrics:[]};}}};
 await mountManagementWorkspace(context);await handle.activate('management-collections','management-loan-operations');
 fire(root.querySelector('[data-loan-ops-tab="audits"]'),'click');assert.equal(root.querySelector('[data-loan-ops-panel="audits"]').getAttribute('hidden'),null);
 const q=root.querySelector('#management-loan-operations-search').querySelector('[name="q"]'),status=root.querySelector('#management-loan-operations-search').querySelector('[name="status"]');q.value='Synthetic receipt';status.value='voided';
 await handle.refreshVisible();assert.match(calls.at(-1),/q=Synthetic%20receipt&status=voided/);assert.equal(root.querySelector('#management-loan-operations-search').querySelector('[name="q"]'),q);
 await handle.activate('management-collections','management-past-due-report');const area=root.querySelector('#management-past-due-report-search').querySelector('[name="area"]');area.value='Synthetic zone';
 await handle.refreshVisible();assert.match(calls.at(-1),/area=Synthetic%20zone/);assert.equal(root.querySelector('#management-past-due-report-search').querySelector('[name="area"]'),area);
});

test('late report search cannot overwrite newer filters or an aborted workspace',async t=>{
 const root=new Element(),abort=new AbortController(),pending=[];t.after(()=>abort.abort());let handle,delay=false;
 await mountManagementWorkspace({root,signal:abort.signal,session:{user:{id:'owner',role:'management'},permissions:[]},setNavigation(){},registerWorkspaceHandle(h){handle=h;},api:{async request(path){if(path.includes('loan-operations')){if(delay)return new Promise(resolve=>pending.push(resolve));return {entries:[],audits:[]};}return {profile:{}};}}});
 await handle.activate('management-collections','management-loan-operations');delay=true;
 const first=handle.refreshVisible();await tick();const second=handle.refreshVisible();await tick();pending[1]({entries:[{client_name:'New current record'}],audits:[]});await second;pending[0]({entries:[{client_name:'Old stale record'}],audits:[]});await first;
 assert.match(root.querySelector('#management-loan-operations-results').textContent,/New current record/);assert.doesNotMatch(root.querySelector('#management-loan-operations-results').textContent,/Old stale record/);
 const last=handle.refreshVisible();await tick();abort.abort();pending[2]({entries:[{client_name:'After abort'}],audits:[]});await last;assert.doesNotMatch(root.querySelector('#management-loan-operations-results').textContent,/After abort/);
});
