import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateSurplusCommand,validateSurplusResult} from '../assets/collector-surplus-contract.js';
import {buildSurplusCommand} from '../assets/collector-surplus.js';
import {createTreasuryClient} from '../assets/treasury-api.js';
const {examples}=JSON.parse(await readFile(new URL('./fixtures/collector-surplus-backend.json',import.meta.url),'utf8'));
const get=k=>structuredClone(examples.find(e=>e.kind===k));
const id='38000000-0000-4000-8000-000000000099';

test('count command binds the explicitly selected held cash to its reviewed version',()=>{
 const e=get('collector_count_record'),preview={...get('preview').response.data,retained_exception_id:id,retained_exception_version:2,retained_cash_amount:'9900.00',physical_cash_required:'100.00'};
 const account={id:e.command.account_id,version:e.command.expected_version};
 const values={...e.command,retained_exception_id:id};delete values.source_digest;delete values.request_id;delete values.account_id;delete values.expected_version;delete values.action;
 const command=buildSurplusCommand(e.command.action,values,{account,records:new Map(),preview});
 assert.equal(command.retained_exception_id,id);assert.equal(command.retained_exception_version,2);
 assert.throws(()=>buildSurplusCommand(e.command.action,{...values,retained_exception_id:null},{account,records:new Map(),preview}));
 assert.throws(()=>validateSurplusCommand({...command,retained_exception_version:null}));
});

test('count result cannot omit or alter the reviewed held portion',()=>{
 const e=get('collector_count_record'),v=e.response.data;
 Object.assign(e.command,{retained_exception_id:id,retained_exception_version:2});
 Object.assign(v.result.count,{retained_exception_id:id,retained_exception_version:2,retained_cash_amount:'9900.00'});
 const reference={...get('preview').response.data,retained_exception_id:id,retained_exception_version:2,retained_cash_amount:'9900.00'};
 const held={options:{body:e.command},actor:e.actor,accountId:v.result.account_id,contextId:v.result.ledger_context_id,collectorId:v.result.count.collector_user_id,reference};
 assert.equal(validateSurplusResult(v,held),v);
 for(const change of [{retained_cash_amount:'0.00'},{retained_exception_id:null},{retained_exception_version:3}]){
  const bad=structuredClone(v);Object.assign(bad.result.count,change);assert.throws(()=>validateSurplusResult(bad,held));
 }
});

test('preview sends explicit exception selection and rejects a mismatched server selection',async()=>{
 const e=get('preview'),p={...e.response.data,retained_exception_id:id,retained_exception_version:2,retained_cash_amount:'9900.00',physical_cash_required:'100.00',gross_obligation:'10000.00',refund_due_total:'0.00'},base=get('staff-workspace-credits').response.data;
 const account=base.accounts.find(a=>a.id===p.account_id);account.version=p.account_version;account.kind='physical_cash';
 const session={user:{id:e.actor.user_id,role:'management',status:'active'},device_id:'synthetic',device_registered:true,permissions:[]};
 let sent,change={};
 const client=createTreasuryClient({request:async(path,options)=>{
  if(path.includes('/workspace'))return {...base,actor:e.actor};
  sent=options.body;return {...p,...change};
 }},{getSession:()=>session});
 try{
  await client.surplusWorkspace();
  await client.surplusPreview(p.remittance_id,p.account_id,{id,version:2});
  assert.equal(sent.retained_exception_id,id);assert.equal(sent.retained_exception_version,2);
  for (const bad of [{retained_exception_version:3},{retained_cash_amount:undefined},{retained_cash_amount:null},{retained_cash_amount:'0.00'}]){
   change=bad;await assert.rejects(client.surplusPreview(p.remittance_id,p.account_id,{id,version:2}));
  }
 }finally{client.dispose();}
});
