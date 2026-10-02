import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const A='00000000-0000-4000-8000-000000000001',B='00000000-0000-4000-8000-000000000002';
const session={user:{id:'manager'},permissions:['accounting.view']};
const pack=id=>({statements:{period:{period_id:id,label:id===A?'August':'September'},profit_or_loss:{},financial_position:{}}});
test('period controls use actual fiscal periods and reject a mismatched pack while keeping local Retry',async()=>{
 const mod=await import('../assets/management-financial-statements.js');assert.equal(typeof mod.mountManagementFinancialStatements,'function');
 const root=new Element(),calls=[];let wrong=true;
 const h=mod.mountManagementFinancialStatements({root,getSession:()=>session,api:{async request(path){calls.push(path);if(path.endsWith('/financial-accounting'))return {fiscal_periods:[{period_id:A,label:'August'},{period_id:B,label:'September'}]};return pack(path.includes(B)&&!wrong?B:A);}}});
 await h.refresh();const select=root.querySelector('[data-statement-period]');assert.equal(select.value,A);
 select.value=B;fire(select,'change');await tick();assert.match(calls.at(-1),new RegExp(`period_id=${B}`));assert.match(root.textContent,/selected period/);assert.equal(root.querySelector('[data-statement-retry]').hidden,false);
 wrong=false;fire(root.querySelector('[data-statement-retry]'),'click');await tick();assert.equal(root.querySelector('[data-statement-period]'),select);assert.match(root.querySelector('[data-statement-results]').textContent,/September/);h.dispose();
});
test('late statements and aborted reads cannot replace the selected period',async()=>{
 const mod=await import('../assets/management-financial-statements.js');assert.equal(typeof mod.mountManagementFinancialStatements,'function');
 const root=new Element(),pending=[],controller=new AbortController();
 const h=mod.mountManagementFinancialStatements({root,getSession:()=>session,signal:controller.signal,api:{async request(path){if(path.endsWith('/financial-accounting'))return {fiscal_periods:[{period_id:A},{period_id:B}]};return new Promise(resolve=>pending.push(resolve));}}});
 const first=h.refresh();await tick();const select=root.querySelector('[data-statement-period]');select.value=B;fire(select,'change');await tick();pending[1](pack(B));await tick();pending[0](pack(A));await first;assert.match(root.querySelector('[data-statement-results]').textContent,/September/);
 const last=h.refresh();await tick();controller.abort();pending[2](pack(A));await last;assert.doesNotMatch(root.querySelector('[data-statement-results]').textContent,/August/);
});
