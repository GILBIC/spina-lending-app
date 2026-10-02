import test from 'node:test';
import assert from 'node:assert/strict';
const workspace=await import('../assets/client-workspace-state.js').catch(()=>({}));
import * as schedule from '../assets/client-schedule.js';
import {loanCard} from '../assets/roles/client.js';
const loan={loan_id:'one',loan_type_name:'7x7',status:'active'};
const saved={loan_id:'one',read_only:true,rows:[],penalty_status:'penalty_outstanding',exact_payoff_total:'2205.00',assessed_penalty_balance:'105.00'};
test('preload error is visible and same-loan retry updates summary and detail',async()=>{
 const reads=workspace.createClientReadController({});let fail=true;
 const schedules=schedule.createClientScheduleController({reads,api:{request:async()=>{if(fail)throw Error('offline');return saved;}}});
 await schedules.load('one');assert.match(loanCard(loan,schedules.get('one')),/Payoff information unavailable/);
 fail=false;await schedules.load('one',{refresh:true});assert.match(loanCard(loan,schedules.get('one')),/2,205/);assert.match(schedule.renderClientSchedule(schedules.get('one').data),/105/);
});
test('review required hides confirmed payoff and missing money is not zero',()=>{
 assert.doesNotMatch(schedule.renderClientSchedule({...saved,penalty_status:'management_review_required'}),/Exact payoff/);
 assert.match(schedule.renderClientSchedule({...saved,exact_payoff_total:null}),/Unavailable/);
});
test('wrong loan and late result rejected; simultaneous ordinary reads deduplicate',async()=>{
 const reads=workspace.createClientReadController({});let resolve;let count=0;
 const c=schedule.createClientScheduleController({reads,api:{request:()=>{count++;return new Promise(r=>resolve=r);}}});
 const a=c.load('one');const b=c.load('one');assert.equal(count,1);resolve({...saved,loan_id:'other'});await Promise.all([a,b]);assert.equal(c.get('one').status,'error');
 const pending=c.load('one',{refresh:true});c.dispose();resolve(saved);await pending;assert.notEqual(c.get('one').status,'ready');
});

