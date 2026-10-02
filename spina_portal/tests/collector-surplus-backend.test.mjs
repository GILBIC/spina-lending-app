import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateSurplusCommand,validateSurplusResult,validateSurplusWorkspace,validateSurplusMovement} from '../assets/collector-surplus-contract.js';
const fixture=JSON.parse(await readFile(new URL('./fixtures/collector-surplus-backend.json',import.meta.url),'utf8'));
test('strict Web contracts accept serialized disposable-service phases, zero PASS and own projections',()=>{
 assert.equal(fixture.synthetic_only,true);
 const records=new Map();let count=0;
 for(const example of fixture.examples){const value=example.response.data,body=example.command;
  if(example.kind==='preview'){assert.ok(Array.isArray(value.source_items));records.set(value.remittance_id,value);continue;}
  if(example.kind.includes('workspace')){assert.equal(validateSurplusWorkspace(value,{actorId:example.actor.user_id,kind:value.kind,limit:value.limit,offset:value.offset}),value);continue;}
  if(body.action.startsWith('collector_')){validateSurplusCommand(body);const refId=body.credit_id??body.case_id??body.count_id??body.action_id??body.anchor_id??body.remittance_id??body.opening_id,reference=records.get(refId)??(body.action==='collector_count_record'?value.result.count:null);assert.ok(reference,example.kind+' reviewed source');
   const r=value.result;try{assert.equal(validateSurplusResult(value,{options:{body},actor:example.actor,accountId:r.account_id,contextId:r.ledger_context_id,collectorId:reference.collector_user_id??body.collector_user_id,own:body.account_id===undefined,reference}),value,example.kind);}catch(e){e.message=example.kind+": "+e.message;throw e;}count++;
  }
  for(const row of Object.values(value.result??{}))if(row&&typeof row==='object'&&row.id)records.set(row.id,row);
  const linked=value.result?.event?.source_link?.action_record??value.result?.source_link?.action_record;if(linked)records.set(linked.id,linked);
 }
 assert.equal(count,16);
});
test('actual return debit stays confirmation pending and mismatched source principal cannot become paid',()=>{
 const e=fixture.examples.find(x=>x.kind==='disbursement_record'),body=e.command,result=e.response.data.result,action=fixture.examples.find(x=>x.kind==='collector_surplus_return_prepare').response.data.result.action_record;
 const source={id:action.id,amount:action.amount,payee_id:action.collector_user_id,destination:action.destination};
 assert.equal(validateSurplusMovement(result,body,source),result);
 for(const changed of [{...result,source_link:{...result.source_link,status:'paid'}},{...result,source_link:{...result.source_link,action_record:{...result.source_link.action_record,amount:'39.00'}}},{...result,event:{...result.event,fee:'0.01'}}])assert.throws(()=>validateSurplusMovement(changed,body,source));
});
test('partial reversal retains original debit principal and normalizes the same instant safely',()=>{
 const e=fixture.examples.find(x=>x.kind==='collector_surplus_return_reverse'),reference=fixture.examples.find(x=>x.kind==='collector_surplus_return_record').response.data.result.action_record,value=e.response.data,held={options:{body:e.command},actor:e.actor,accountId:value.result.account_id,contextId:value.result.ledger_context_id,collectorId:reference.collector_user_id,reference};
 assert.equal(validateSurplusResult({...value,result:{...value.result,incoming_event:{...value.result.incoming_event,effective_at:new Date(e.command.effective_at).toISOString()}}},held).result.action_record.amount,reference.amount);
 assert.throws(()=>validateSurplusResult({...value,result:{...value.result,action_record:{...value.result.action_record,amount:e.command.amount}}},held));
});
test('activated opening must create only its exact evidenced obligation and amount',()=>{
 const e=fixture.examples.find(x=>x.kind==='collector_surplus_opening_activate'),reference=fixture.examples.find(x=>x.kind==='collector_surplus_opening_prepare').response.data.result.opening_anchor,value=e.response.data,held={options:{body:e.command},actor:e.actor,accountId:value.result.account_id,contextId:value.result.ledger_context_id,collectorId:reference.collector_user_id,reference};
 assert.throws(()=>validateSurplusResult({...value,result:{...value.result,credit:{...value.result.credit,recognized_amount:'99.00'}}},held));
});

test('real blocked actual debit preserves reserved source and exact claimed event binding',()=>{const e=fixture.examples.find(x=>x.command?.action==='disbursement_record'&&x.response.data.result.source_link.status==='blocked'),result=e.response.data.result,action=result.source_link.action_record,source={id:action.id,amount:action.amount,payee_id:action.collector_user_id,destination:action.destination};assert.equal(validateSurplusMovement(result,e.command,source),result);for(const link of [{...result.source_link,source_id:e.command.account_id},{...result.source_link,observed_event_id:action.id},{...result.source_link,action_record:{...action,status:'paid'}}])assert.throws(()=>validateSurplusMovement({...result,source_link:link},e.command,source));});
