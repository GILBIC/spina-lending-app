import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element} from './helpers/dom.mjs';
import {clientInstallmentGuidance,validateClientSchedule,renderClientPayoff,renderClientSchedule,formatAuthoritativeMoney} from '../assets/client-schedule.js';
import {mountClientWorkspace} from '../assets/roles/client.js';

const today='2026-10-02';
const row=(date=today,amount='40.00')=>({payment_date:date,status:date===today?'Due Today':'Scheduled',amount:'100.00',details:{remaining_amount:amount}});
const saved=(rows=[row()])=>({loan_id:'one',read_only:true,rows,snapshot_day:today,penalty_status:'penalty_outstanding',exact_payoff_total:'2205.00',assessed_penalty_balance:'105.00',projected_penalty:'0.00',past_due_amount:'105.00',past_due_count:2});
const guidance=data=>clientInstallmentGuidance({scheduleState:{status:'ready',data},today});

for(const value of ['bad',true,false,{},[],[40],'1e3','NaN','1,2',40,0,null,''])test(`invalid schedule money remains unavailable (${JSON.stringify(value)})`,()=>{
 const data={...saved([row(today,value)]),exact_payoff_total:value,assessed_penalty_balance:value,projected_penalty:value,past_due_amount:value};
 const result=guidance(data);
 assert.equal(result.status,'unavailable');assert.equal(result.selectedRow,null);assert.equal(result.pastDueAmount,null);
 const payoff=new Element();payoff.innerHTML=renderClientPayoff(data);
 assert.equal(payoff.querySelector('p').textContent,'Unavailable');
 for(const amount of payoff.querySelectorAll('.detail-item'))assert.match(amount.textContent,/Unavailable/);
});

test('earliest unpaid future row with unavailable amount cannot be skipped for a later date',()=>{
 const result=guidance(saved([row('2026-10-03',null),row('2026-10-04','40.00')]));
 assert.equal(result.selectedRow,null);assert.equal(result.status,'unavailable');
});

test('fixed-point zero, signed and large server strings retain their digits and independent facts',()=>{
 for(const [value,display]of [['0.00','₱0.00'],['-1.25','-₱1.25'],['90071992547409.93','₱90,071,992,547,409.93']]){
  const result=guidance({...saved([row(today,value)]),past_due_amount:value});
  assert.equal(result.selectedRow.details.remaining_amount,value);assert.equal(result.pastDueAmount,value);assert.match(result.message,new RegExp(display.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
 }
 assert.equal(formatAuthoritativeMoney('1,2'),'₱12','the exported display formatter remains compatible for existing callers');
 for(const status of ['Paid','No Collection'])assert.equal(guidance(saved([{...row(),status,details:{remaining_amount:'0.00'}}])).status,'covered');
 assert.doesNotMatch(renderClientPayoff({...saved(),penalty_status:'management_review_required'}),/Exact payoff/);
});

for(const date of ['2026-02-30','2026-02-29','2026-04-31','0000-01-01'])test(`impossible calendar date is rejected without normalization (${date})`,()=>{
 assert.throws(()=>validateClientSchedule(saved([row(date)]),'one'));
 assert.equal(clientInstallmentGuidance({scheduleState:{status:'ready',data:{...saved([row(date)]),snapshot_day:date}},today:date}).status,'unavailable');
});

test('real leap days remain valid and a snapshot from yesterday remains stale',()=>{
 for(const date of ['2028-02-29','2026-02-28','0001-01-01'])assert.equal(validateClientSchedule(saved([row(date)]),'one').rows[0].payment_date,date);
 assert.equal(clientInstallmentGuidance({scheduleState:{status:'ready',data:saved()},today:'2026-10-03'}).status,'stale');
});

test('invalid optional maturity dates stay unavailable without normalizing into another day',()=>{
 const root=new Element();root.innerHTML=renderClientSchedule({...saved(),contractual_maturity:'2026-02-30',operational_maturity:'2026-04-31'},{today});
 for(const label of ['Contractual maturity','Current operational completion'])assert.match(root.querySelectorAll('.detail-item').find(node=>node.textContent.startsWith(label)).textContent,/Unavailable/);
});

test('malformed past-due counts are unavailable rather than truthy or negative record counts',()=>{
 for(const value of [true,'2',{},-1,1.5]){
  const data={...saved(),past_due_count:value};assert.equal(guidance(data).pastDueCount,null);
  const root=new Element();root.innerHTML=renderClientSchedule(data,{today});
  assert.match(root.querySelectorAll('.detail-item').find(node=>node.textContent.startsWith('Past-due rows')).textContent,/Unavailable/);
 }
 assert.equal(guidance({...saved(),past_due_count:0}).pastDueCount,0);
});

test('mounted Today, summary and expanded source never coerce invalid money, then recover current exact facts',async t=>{
 const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let handle,current={...saved(),past_due_amount:[40],exact_payoff_total:[40]};const calls=[];
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path){calls.push(path);if(path.endsWith('/loans'))return {loans:[{loan_id:'one',loan_number:'Synthetic loan',status:'active',loan_type_name:'7x7',daily_amount:'100.00'}]};if(path.endsWith('/schedule'))return current;if(path.endsWith('activity-notifications'))return [];return {};}}};
 await mountClientWorkspace(context);await setImmediate();await setImmediate();
 assert.match(root.querySelector('[data-client-home-loans]').textContent,/Server past due Unavailable/);
 assert.doesNotMatch(root.querySelector('[data-client-loan-summary]').textContent,/₱40/);
 current=saved();await context.clientSchedules.load('one',{refresh:true});
 assert.match(root.querySelector('[data-client-home-loans]').textContent,/Server past due ₱105.00/);
 assert.match(root.querySelector('[data-client-loan-summary]').textContent,/₱2,205.00/);
 assert.equal(calls.filter(path=>path.endsWith('/schedule')).length,2);
 handle.dispose();
});
