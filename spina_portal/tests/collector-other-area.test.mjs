import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {createCollectorWriteGuard} from '../assets/collector-write-guard.js';
const module=await import('../assets/collector-other-area.js').catch(()=>({}));
const entry={route_entry_id:'route',client_id:'client',loan_id:'loan',route_revision:'v1',client_name:'Other client',assigned_collector_name:'Original collector',loan_type:'Regular',can_collect_mobile:true,can_enter_payment:true,daily_amount:'100.01'};
test('other-area rows preserve owner and suppress unavailable/processed writes',()=>{
  let html=module.renderOtherAreaEntries([entry]);assert.match(html,/Original collector/);assert.match(html,/data-other-payment/);
  html=module.renderOtherAreaEntries([{...entry,processed_today:true,today_collector_name:'Recorder'}]);assert.doesNotMatch(html,/data-other-payment/);assert.match(html,/Recorder/);
  html=module.renderOtherAreaEntries([{...entry,can_collect_mobile:false}]);assert.doesNotMatch(html,/data-other-payment/);
});
test('cross-area payment preserves route identity and needs recorder confirmation',async()=>{
  const root=new Element();const calls=[];let saved=0;
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=module.mountCollectorOtherArea({root,session:{permissions:['collection.create']},routeDate:'2026-09-28',guard,identity:()=>({deviceId:'web',deviceSequence:3,clientTransactionId:'11111111-2222-4333-8444-555555555555'}),onSaved:async()=>{saved++;},api:{request:async(path,options)=>{calls.push({path,options});return options?.method==='POST' ? {status:'accepted',client_transaction_id:options.body.client_transaction_id,receipt_number:'receipt'} : [entry];}}});
  root.querySelector('[name="query"]').value='Other client';fire(root.querySelector('[data-other-search]'),'submit');await setImmediate();
  assert.match(calls[0].path,/other-area-clients\/search\?q=Other%20client/);
  const form=root.querySelector('[data-other-payment]');form.querySelector('[name="amount"]').value='100.01';
  fire(form,'submit');await setImmediate();assert.equal(calls.length,1);
  form.querySelector('[name="recorderConfirmation"]').checked=true;fire(form,'submit');await setImmediate();
  assert.equal(calls[1].options.body.route_revision,'v1');assert.equal(calls[1].options.body.loan_id,'loan');assert.equal(calls[1].options.body.amount,'100.01');assert.equal(calls[1].options.financial,true);assert.equal(saved,1);dispose();guard.dispose();
});

test('other-area remittance requires a current recipient preview and preserves recipient capacity',async()=>{
  const root=new Element();const calls=[];let saved=0;
  const targets=[{recipient_user_id:'owner',recipient_name:'Owner',recipient_capacity:'assigned_collector',role_name:'Assigned Collector',total_amount:'100.01'},{recipient_user_id:'manager',recipient_name:'Manager',recipient_capacity:'management',role_name:'Management',total_amount:'100.01'}];
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=module.mountCollectorOtherArea({root,session:{permissions:['collection.create','remittance.create','remittance.view']},routeDate:'2026-09-28',guard,onSaved:async()=>{saved++;},api:{request:async(path,options)=>{calls.push({path,options});if(path.includes('/targets'))return targets;if(path.includes('/history'))return [];if(path.includes('/preview'))return {total_amount:'100.01',transaction_count:1,client_count:1,items:[{client_name:'Client',amount:'100.01'}]};return {remittance_id:'cross-id',remittance_number:'CROSS1',recipient_user_id:options.body.recipient_user_id,recipient_capacity:options.body.recipient_capacity,collection_date:options.body.collection_date};}}});
  await setImmediate();const form=root.querySelector('[data-cross-form]');assert.ok(form);
  fire(form,'submit');await setImmediate();assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
  fire(form.querySelector('[data-cross-preview]'),'click');await setImmediate();
  form.querySelector('[name="recipient"]').value='1';fire(form.querySelector('[name="recipient"]'),'change');fire(form,'submit');await setImmediate();assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
  fire(form.querySelector('[data-cross-preview]'),'click');await setImmediate();fire(form,'submit');await setImmediate();
  const post=calls.find(call=>call.options?.method==='POST');assert.equal(post.path,'/api/v1/collector/cross-remittances');assert.equal(post.options.body.recipient_user_id,'manager');assert.equal(post.options.body.recipient_capacity,'management');assert.equal(post.options.financial,true);assert.equal(saved,1);dispose();guard.dispose();
});

test('missing authoritative route date and disposed searches cannot enable collection',async()=>{
  const root=new Element();const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  module.mountCollectorOtherArea({root,session:{permissions:['collection.create']},routeDate:null,guard,api:{request:async()=>{throw new Error('Must not call');}}});assert.equal(root.querySelector('[data-other-search]'),null);
  let resolve;
  const dispose=module.mountCollectorOtherArea({root,session:{permissions:['collection.create']},routeDate:'2026-09-28',guard,api:{request:()=>new Promise(done=>{resolve=done;})}});
  root.querySelector('[name="query"]').value='Client';fire(root.querySelector('[data-other-search]'),'submit');dispose();resolve([entry]);await setImmediate();assert.equal(root.querySelector('[data-other-payment]'),null);guard.dispose();
});
