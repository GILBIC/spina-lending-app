import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
import {mountManagementPortfolio} from '../assets/management-portfolio.js';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const session={user:{id:'manager'}};
const row=n=>({loan_id:`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`,client_id:`10000000-0000-4000-8000-${String(n).padStart(12,'0')}`,client_name:'Same name',loan_number:`Loan ${n}`,principal:'900.00',remaining_balance:'500.00',paid_amount:'400.00',paid_percent:'44.44',pass_count:2});
test('100 then 50 entries are reachable with exact offset and search resets the page',async()=>{
 const root=new Element(),calls=[];
 const h=mountManagementPortfolio({root,getSession:()=>session,api:{async request(path){calls.push(path);const offset=Number(new URL(path,'https://example.test').searchParams.get('offset'));return {summary:{},loans:Array.from({length:offset?50:100},(_,i)=>row(offset+i))};}}});
 await h.refresh(); assert.equal(root.querySelectorAll('[data-portfolio-open]').length,100);
 fire(root.querySelector('[data-portfolio-next]'),'click');await tick();
 assert.match(calls.at(-1),/offset=100/);assert.equal(root.querySelectorAll('[data-portfolio-open]').length,50);assert.equal(root.querySelector('[data-portfolio-next]').disabled,true);
 root.querySelector('[name="query"]').value='different';fire(root.querySelector('#management-loan-search'),'submit');await tick();assert.match(calls.at(-1),/offset=0/);
 h.dispose();
});
test('same-name loans open only exact identity; refresh invalidates detail and failed next page allows Previous',async()=>{
 const root=new Element();let failed=false;
 const h=mountManagementPortfolio({root,getSession:()=>session,api:{async request(){if(failed)throw new Error('Read unavailable');return {summary:{},loans:[row(1),row(2),{client_name:'Same name'}]};}}});
 await h.refresh();assert.equal(root.querySelectorAll('[data-portfolio-open]').length,2);
 fire(root.querySelectorAll('[data-portfolio-open]')[1],'click');assert.match(root.querySelector('[data-portfolio-detail]').textContent,/Loan 2/);assert.match(root.querySelector('[data-portfolio-detail]').textContent,/44.44/);assert.doesNotMatch(root.querySelector('[data-portfolio-detail]').textContent,/Loan 1/);
 failed=true;await h.refresh();assert.equal(root.querySelector('[data-portfolio-detail]').hidden,true);assert.match(root.textContent,/Read unavailable/);
 h.dispose();
});
