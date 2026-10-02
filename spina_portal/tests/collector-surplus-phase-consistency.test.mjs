import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {createTreasuryClient} from '../assets/treasury-api.js';import {validateSurplusResult} from '../assets/collector-surplus-contract.js';
const {examples}=JSON.parse(await readFile(new URL('./fixtures/collector-surplus-backend.json',import.meta.url),'utf8'));
const get=k=>examples.find(e=>e.kind===k),base=get('staff-workspace-credits').response.data;
const probes=[
 {kind:'collector_count_record',page:'remittances',reference:get('preview').response.data,change:r=>{r.disposition='counted_short_rejected';}},
 {kind:'collector_surplus_return_acknowledge',page:'credits',reference:get('collector_surplus_return_prepare').response.data.result.credit,change:r=>{r.disposition='acknowledged_not_received';}},
 {kind:'collector_surplus_return_prepare',page:'credits',reference:get('collector_surplus_recognize').response.data.result.credit,change:r=>{r.action_record.status='paid';}},
];
for(const probe of probes)test(`${probe.kind} cannot contradict its returned phase or unlock an ambiguous request`,async()=>{
 const e=get(probe.kind),body=e.command,value=structuredClone(e.response.data),result=value.result,reference=probe.reference,held={options:{body},actor:e.actor,accountId:result.account_id,contextId:result.ledger_context_id,collectorId:reference.collector_user_id,reference};
 assert.equal(validateSurplusResult(value,held),value);probe.change(result);assert.throws(()=>validateSurplusResult(value,held));
 const projection={...base,actor:e.actor,kind:probe.page,items:[reference],total_count:1,totals:{},accounts:base.accounts.map(a=>({...a,version:body.expected_version??a.version})),capabilities:{...base.capabilities,return_acknowledge:true}},session={user:{id:e.actor.user_id,role:'management',status:'active'},device_id:'synthetic',device_registered:true,permissions:[]};let posts=0;
 const client=createTreasuryClient({request:async(p,o={})=>{if(p.includes('/workspace'))return projection;if(p.includes('/requests/'))return value;if(o.financial){posts++;return value;}throw Error('Unexpected read '+p);}},{getSession:()=>session});try{await client.surplusWorkspace({kind:probe.page,mode:'staff'});await assert.rejects(client.execute(body),{code:'treasury_result_unverified'});assert.equal(client.state().status,'uncertain');await assert.rejects(client.recover(),{code:'treasury_result_unverified'});assert.equal(client.state().status,'uncertain');await assert.rejects(client.execute({...body,request_id:crypto.randomUUID()}));assert.equal(posts,1);}finally{client.dispose();}
});
