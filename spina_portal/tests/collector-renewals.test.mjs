import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {createCollectorWriteGuard} from '../assets/collector-write-guard.js';
import {mountCollectorWorkspace} from '../assets/roles/collector.js';
const module=await import('../assets/collector-renewals.js').catch(()=>({}));
const session={permissions:['renewal.recommend.assigned','renewal.cash_custody.assigned']};
const record={request_id:'renewal',client_name:'Synthetic <client>',status:'approved',net_release_amount:'1250.01',cash_released_to_collector_at:'2026-09-28T02:00:00Z',handover_proof_status:'none'};

test('custody-only Collector loads assigned handovers without recommendation controls',async()=>{
  const root=new Element();const calls=[];let saved=0;
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=module.mountCollectorRenewals({root,session:{permissions:['renewal.cash_custody.assigned']},guard,onSaved:async()=>{saved++;},api:{request:async(path,options)=>{calls.push({path,options});return options ? {request:record} : {requests:[record,{...record,request_id:'pending',status:'pending'}]};}}});
  try {
    await setImmediate();
    assert.equal(calls[0]?.path,'/api/v1/collector/renewals');
    assert.equal(root.querySelector('[data-renewal-action="recommendation"]'),null);
    const form=root.querySelector('[data-renewal-action="cash-received"]');assert.ok(form);
    form.querySelector('[name="physicalConfirmation"]').checked=true;fire(form,'submit');await setImmediate();
    assert.equal(calls[1].path,'/api/v1/collector/renewals/renewal/cash-received');assert.equal(saved,1);
  } finally {dispose();guard.dispose();}
});

test('custody-only workspace exposes and loads Renewal handover navigation',async()=>{
  const controller=new AbortController();const root=new Element();root.dataset={};const calls=[];let navigation=[];
  const context={root,session:{user:{role:'collector',roles:['collector']},permissions:['renewal.cash_custody.assigned']},signal:controller.signal,setNavigation:items=>{navigation=items;},api:{request:async path=>{calls.push(path);return path==='/api/v1/collector/renewals'?{requests:[record]}:{};}}};
  try {
    await mountCollectorWorkspace(context);await setImmediate();
    assert.ok(navigation.some(item=>item.id==='collector-renewals'));
    assert.ok(root.querySelector('#collector-renewals')?.querySelector('[data-renewal-action="cash-received"]'));
    assert.equal(calls.filter(path=>path==='/api/v1/collector/renewals').length,1);
  } finally {controller.abort();}
});
test('cash controls follow authoritative handover stages and distinct permissions',()=>{
  assert.deepEqual(module.collectorRenewalActions(record,session),['cash-received']);
  assert.deepEqual(module.collectorRenewalActions({...record,collector_cash_received_at:'now'},session),['cash-given']);
  assert.deepEqual(module.collectorRenewalActions({...record,collector_cash_received_at:'now',cash_given_to_client_at:'now'},session),['handover-photo']);
  assert.deepEqual(module.collectorRenewalActions({...record,collector_cash_received_at:'now',cash_given_to_client_at:'now',handover_proof_status:'under_review'},session),[]);
  assert.deepEqual(module.collectorRenewalActions(record,{permissions:['renewal.recommend.assigned']}),[]);
});
test('pending recommendation does not expose amount approval, identity verification or activation',()=>{
  const html=module.renderCollectorRenewals([{...record,status:'pending'}],session);
  assert.match(html,/recommendation/);assert.match(html,/Synthetic &lt;client&gt;/);
  assert.doesNotMatch(html,/name="approved_principal"|Activate loan|selfie_verified/);
});
test('handover posts only after physical confirmation and locks uncertain results',async()=>{
  const root=new Element();const calls=[];let saved=0;
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const dispose=module.mountCollectorRenewals({root,session,guard,onSaved:async()=>{saved++;},api:{request:async(path,options)=>{calls.push({path,options});if(!options)return {requests:[record]};throw Object.assign(new Error('Refresh authoritative record.'),{code:'network_uncertain'});}}});
  await setImmediate();const form=root.querySelector('[data-renewal-action="cash-received"]');assert.ok(form);
  fire(form,'submit');await setImmediate();assert.equal(calls.length,1);
  form.querySelector('[name="physicalConfirmation"]').checked=true;fire(form,'submit');await setImmediate();
  assert.equal(calls[1].path,'/api/v1/collector/renewals/renewal/cash-received');assert.equal(calls[1].options.financial,true);assert.equal(guard.locked,true);assert.equal(saved,0);
  fire(form,'submit');await setImmediate();assert.equal(calls.length,2);dispose();guard.dispose();
});

test('handover photo validates file type and size, then uses existing private upload endpoint',async()=>{
  const root=new Element();const calls=[];let saved=0;
  const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});
  const item={...record,collector_cash_received_at:'now',cash_given_to_client_at:'now'};
  const dispose=module.mountCollectorRenewals({root,session,guard,onSaved:async()=>{saved++;},api:{request:async(path,options)=>{calls.push({path,options});return options ? {status:'under_review'} : {requests:[item]};}}});
  await setImmediate();const form=root.querySelector('[data-renewal-action="handover-photo"]');const input=form.querySelector('[name="photo"]');
  for(const file of [{name:'invalid.svg',type:'image/svg+xml',size:10},{name:'large.jpg',type:'image/jpeg',size:8*1024*1024+1}]){input.files=[file];fire(form,'submit');await setImmediate();}
  assert.equal(calls.length,1);
  const file={name:'handover.jpg',type:'image/jpeg',size:1234};input.files=[file];fire(form,'submit');await setImmediate();
  assert.equal(calls[1].path,'/api/v1/collector/renewals/renewal/handover-photo');assert.equal(calls[1].options.rawBody,file);assert.equal(calls[1].options.headers['Content-Type'],'image/jpeg');assert.equal(saved,1);dispose();guard.dispose();
});

test('nonrecommendation requires explanation and permission denial makes no API call',async()=>{
  const root=new Element();const guard=createCollectorWriteGuard({eventTarget:new EventTarget(),onLock:()=>{}});const calls=[];
  const api={request:async(path,options)=>{calls.push({path,options});return options ? {request:{...record,request_id:'renewal'}} : {requests:[{...record,status:'pending'}]};}};
  const denied=module.mountCollectorRenewals({root,session:{permissions:[]},guard,api});assert.equal(calls.length,0);denied();
  const dispose=module.mountCollectorRenewals({root,session,guard,api,onSaved:async()=>{}});await setImmediate();const form=root.querySelector('[data-renewal-action="recommendation"]');
  form.querySelector('[name="recommendation"]').value='do_not_recommend';form.querySelector('[name="reasonCode"]').value='Payment capacity concern';fire(form,'submit');await setImmediate();assert.equal(calls.length,1);
  form.querySelector('[name="comment"]').value='Client reported lower income.';fire(form,'submit');await setImmediate();assert.equal(calls[1].options.body.recommendation,'do_not_recommend');assert.equal(calls[1].options.body.reason_code,'Payment capacity concern');dispose();guard.dispose();
});
