import test from 'node:test';
import assert from 'node:assert/strict';
import {Element,fire} from './helpers/dom.mjs';
import {mountCollectorScheduleView,renderCollectorSchedule,validateCollectorSchedule,collectorScheduleRows} from '../assets/collector-schedule-view.js';
const entry={route_entry_id:'r',loan_id:'l',client_id:'c'};
const schedule={loan_id:'l',client_id:'c',read_only:true,as_of_date:'2026-10-02',schedule_id:'sid',schedule_version:1,contract_reference:'Contract',payment_frequency:'daily',base_maturity:'2026-10-02',updated_maturity:'2026-10-06',maturity_projection_status:'extended',past_due_amount:'100.00',past_due_count:1,exact_payoff_total:'2205.00',assessed_penalty_balance:'105.00',projected_penalty:'50.00',rows:Array.from({length:120},(_,i)=>({installment_id:i,kind:'installment',date:i<60?'2026-10-01':'2026-10-02',amount:'100.00',remaining_amount:'100.00',status:'scheduled'}))};
test('schedule verifies loan client scope and refuses malformed money',()=>{assert.equal(validateCollectorSchedule(schedule,entry),true);for(const bad of [{...schedule,loan_id:'other'},{...schedule,client_id:'other'},{...schedule,read_only:false},{...schedule,exact_payoff_total:'NaN'}])assert.equal(validateCollectorSchedule(bad,entry),false);});
test('payoff assessed and projected penalties remain distinct review suppresses confirmed payoff',()=>{const html=renderCollectorSchedule(schedule);for(const text of ['2,205.00','105.00','50.00','Base maturity','Updated maturity','Contract','Past due'])assert.ok(html.includes(text),text);const review=renderCollectorSchedule({...schedule,management_review_required_reason:'Disputed plan'});assert.match(review,/Disputed plan/);assert.doesNotMatch(review,/Exact payoff total/);});
test('all mode reaches every same date row history uses server as of date',()=>{assert.equal(collectorScheduleRows(schedule,'all').length,120);assert.equal(collectorScheduleRows(schedule,'current').length,60);assert.equal(collectorScheduleRows(schedule,'history').length,60);});
for(const change of ['revision','date'])test(`loaded schedule requires explicit re-review after route ${change} changes`,async()=>{
  const root=new Element();let route={route_date:'2026-10-02',entries:[{...entry,route_revision:'v1'}]},reads=0;
  const handle=mountCollectorScheduleView({root,api:{async request(){reads++;return schedule;}},getSession:()=>({permissions:['route.view']}),getRoute:()=>route});
  await handle.open({routeEntryId:'r',loanId:'l'});assert.match(root.textContent,/2,205\.00/);
  route=change==='date'?{...route,route_date:'2026-10-03'}:{...route,entries:[{...entry,route_revision:'v2'}]};handle.invalidate();
  assert.doesNotMatch(root.textContent,/2,205\.00/);assert.match(root.textContent,/Route changed.*review again/);assert.equal(reads,1);assert.ok(root.querySelector('[data-retry-schedule]'));
  await handle.refresh();assert.equal(reads,2);assert.match(root.textContent,/2,205\.00/);handle.dispose();
});
test('unchanged route refresh retains a pending schedule while changed revision ignores its late response',async()=>{
  for(const changed of [false,true]){
    const root=new Element();let route={route_date:'2026-10-02',entries:[{...entry,route_revision:'v1'}]},resolve;
    const handle=mountCollectorScheduleView({root,api:{request:()=>new Promise(r=>resolve=r)},getSession:()=>({permissions:['route.view']}),getRoute:()=>route});
    const read=handle.open({routeEntryId:'r',loanId:'l'});if(changed)route={...route,entries:[{...entry,route_revision:'v2'}]};handle.invalidate();resolve(schedule);await read;
    if(changed){assert.doesNotMatch(root.textContent,/2,205\.00/);assert.match(root.textContent,/Route changed.*review again/);}else {assert.equal(root.hidden,false);assert.match(root.textContent,/2,205\.00/);}handle.dispose();
  }
});
test('route view only opens read controller without payment and close ignores delayed response',async()=>{const root=new Element();let resolve;const calls=[];const handle=mountCollectorScheduleView({root,api:{request(path){calls.push(path);return new Promise(r=>{resolve=r;});}},getSession:()=>({permissions:['route.view']}),getRoute:()=>({route_date:'2026-10-02',entries:[entry]})});const pending=handle.open({routeEntryId:'r',loanId:'l'});handle.close();resolve(schedule);await pending;assert.equal(root.hidden,true);assert.equal(root.innerHTML,'');assert.deepEqual(calls,['/api/v1/collector/loans/l/schedule']);handle.dispose();});
test('opening schedule immediately focuses its visible detail and late response does not steal focus',async()=>{const root=new Element();let resolve,scrolls=0,focuses=0;root.scrollIntoView=()=>scrolls++;root.focus=()=>focuses++;const opener=new Element('button');const handle=mountCollectorScheduleView({root,api:{request:()=>new Promise(r=>resolve=r)},getSession:()=>({permissions:['route.view']}),getRoute:()=>({route_date:'2026-10-02',entries:[entry]})});const pending=handle.open({routeEntryId:'r',loanId:'l',opener});assert.equal(root.hidden,false);assert.equal(root.getAttribute('tabindex'),'-1');assert.equal(focuses,1);assert.equal(scrolls,1);resolve(schedule);await pending;assert.equal(focuses,1);handle.close();assert.equal(opener.focused,true);handle.dispose();});
