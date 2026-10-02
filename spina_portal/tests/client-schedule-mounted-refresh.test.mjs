import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';

const flush=async()=>{await setImmediate();await setImmediate();};
const saved=(id='one',amount='111.00')=>({loan_id:id,read_only:true,loan_type:'7x7',penalty_status:'penalty_outstanding',exact_payoff_total:amount,assessed_penalty_balance:'105.00',projected_penalty:'0.00',past_due_amount:'10.00',past_due_count:1,rows:Array.from({length:65},(_,index)=>({payment_date:`2050-${String(1+Math.floor(index/28)).padStart(2,'0')}-${String(index%28+1).padStart(2,'0')}`,amount:'100.00',status:'Scheduled',details:{remaining_amount:'40.00',note:`Exact row ${index}`}}))});
async function mounted(t){
  const root=new Element(),abort=new AbortController(),calls=[],results=new Map([['one',()=>Promise.resolve(saved())],['two',()=>Promise.resolve(saved('two','777.00'))]]);let handle;
  const context={root,signal:abort.signal,session:{user:{id:'synthetic-client',role:'client'}},setNavigation(){},registerWorkspaceHandle:h=>handle=h,api:{async request(path,options={}){calls.push({path,method:options.method||'GET'});assert.notEqual(options.method,'POST');const id=path.match(/\/loans\/(one|two)\/schedule$/)?.[1];if(id)return results.get(id)();if(path.endsWith('/loans'))return {loans:['one','two'].map(loan_id=>({loan_id,loan_number:loan_id,loan_type_name:'7x7',status:'active',daily_amount:'100.00'}))};if(path.endsWith('activity-notifications'))return [];return {};}}};
  await mountClientWorkspace(context);t.after(()=>abort.abort());await flush();await handle.activate('client-loans');
  const card=id=>root.querySelector(`[data-client-schedule-loan="${id}"]`).closest('.loan-card'),panel=id=>card(id).querySelector('[data-client-schedule-panel]');
  for(const id of ['one','two']){fire(card(id).querySelector('[data-client-schedule-loan]'),'click');await flush();assert.equal(panel(id).hidden,false,'fixture must open the real bound panel');assert.match(panel(id).textContent,/Exact payoff/);}
  return {root,context,handle,calls,results,card,panel,abort};
}

test('header schedule refresh keeps open detail and summary on the same loading/error/recovered state without losing view or drafts',async t=>{
  const h=await mounted(t),panel=h.panel('one'),summary=h.card('one').querySelector('[data-client-loan-summary]');
  fire(panel.querySelector('[data-schedule-view="all"]'),'click');fire(panel.querySelector('[data-schedule-more]'),'click');assert.match(panel.textContent,/Showing 40 of 65/);
  const support=h.root.querySelector('#client-support-form'),message=support.querySelector('[name="message"]');message.value='Keep this unrelated Client question';
  let reject;h.results.set('one',()=>new Promise((resolve,fail)=>reject=fail));await h.handle.refreshVisible();await flush();
  assert.match(summary.textContent,/Loading payoff/);assert.match(panel.textContent,/Loading authoritative schedule/);assert.doesNotMatch(panel.textContent,/111/);
  reject(Error('Synthetic schedule read failed'));await flush();assert.match(summary.textContent,/Payoff information unavailable/);assert.match(panel.textContent,/Schedule unavailable/);assert.doesNotMatch(panel.textContent,/111/);
  const before=h.calls.length;h.results.set('one',async()=>saved('one','2205.00'));fire(panel.querySelector('[data-schedule-refresh]'),'click');await flush();
  assert.equal(h.calls.length,before+1);assert.match(summary.textContent,/2,205/);assert.match(panel.textContent,/2,205/);assert.match(panel.textContent,/105/);assert.match(panel.textContent,/Showing 40 of 65/);assert.equal(panel.querySelector('[data-schedule-view="all"]').getAttribute('aria-pressed'),'true');
  assert.strictEqual(h.root.querySelector('#client-support-form'),support);assert.equal(message.value,'Keep this unrelated Client question');
});

test('targeted shared refresh changes only the matching open loan; Close and reopen reuse the in-flight read',async t=>{
  const h=await mounted(t),panel=h.panel('one'),other=h.panel('two'),otherRow=other.querySelector('tbody'),otherText=other.textContent;let resolve;
  h.results.set('one',()=>new Promise(done=>resolve=done));const before=h.calls.length,pending=h.context.clientSchedules.load('one',{refresh:true});
  assert.match(panel.textContent,/Loading authoritative schedule/);assert.strictEqual(other.querySelector('tbody'),otherRow);assert.equal(other.textContent,otherText);
  fire(panel.querySelector('[data-schedule-close]'),'click');assert.equal(panel.hidden,true);
  fire(h.card('one').querySelector('[data-client-schedule-loan]'),'click');assert.equal(panel.hidden,false);assert.equal(h.calls.length,before+1);
  fire(panel.querySelector('[data-schedule-close]'),'click');resolve(saved('one','2205.00'));await pending;await flush();assert.equal(panel.hidden,true,'a closed panel must not reopen on a late result');
  fire(h.card('one').querySelector('[data-client-schedule-loan]'),'click');await flush();assert.match(panel.textContent,/2,205/);assert.equal(h.calls.length,before+1);assert.equal(other.textContent,otherText);
});

test('superseded and disposed shared reads never redraw old private panel values',async t=>{
  const h=await mounted(t),panel=h.panel('one');let first,second;
  h.results.set('one',()=>new Promise(done=>first=done));const old=h.context.clientSchedules.load('one',{refresh:true});
  h.results.set('one',()=>new Promise(done=>second=done));const latest=h.context.clientSchedules.load('one',{refresh:true});second(saved('one','2205.00'));await latest;await flush();assert.match(panel.textContent,/2,205/);
  first(saved('one','999.00'));await old;await flush();assert.doesNotMatch(panel.textContent,/999/);assert.match(panel.textContent,/2,205/);
  let late;h.results.set('one',()=>new Promise(done=>late=done));const pending=h.context.clientSchedules.load('one',{refresh:true});h.abort.abort();assert.equal(h.root.innerHTML,'');late(saved());await pending;await flush();assert.equal(h.root.innerHTML,'');
});
