import assert from 'node:assert/strict';
import test from 'node:test';
import {buildSurplusCommand} from '../assets/collector-surplus.js';
import {validateSurplusCommand} from '../assets/collector-surplus-contract.js';
import {validateApplicationPreview,validateApplicationResult} from '../assets/collector-credit-application.js';
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const account={id:id(1),version:3};
const approval={id:id(2),version:1,kind:'application',status:'reserved',event_id:null,amount:'4.00',account_id:id(1),remittance_id:id(3),collector_user_id:id(4),recipient_user_id:id(5),source_digest:'a'.repeat(64)};
const preview={can_count:true,account_id:id(1),remittance_id:id(3),collector_user_id:id(4),recipient_user_id:id(5),source_digest:'b'.repeat(64),remittance_source_digest:'a'.repeat(64),authorized_credit_application:'4.00',gross_obligation:'100.00',refund_due_total:'0.00',physical_cash_required:'96.00',credit_application:approval};
const count={...preview,id:id(6),version:1,credit_application_id:id(2),credit_application_version:1,counted_amount:'96.00',difference:'0.00'};
const fields={remittance_id:id(3),counted_amount:'96.00',counted_at:'2026-10-05T15:00:00+08:00',evidence_id:id(7),recipient_attestation:'Actual counted cash',review_acknowledged:true};
test('record and acceptance retain the selected approval coordinates',()=>{
 const recorded=buildSurplusCommand('collector_count_record',{...fields,credit_application_id:id(2)},{account,preview,records:new Map()});
 assert.equal(recorded.credit_application_id,id(2));assert.equal(recorded.credit_application_version,1);
 const accepted=buildSurplusCommand('collector_count_accept',{count_id:id(6),physical_receipt_acknowledged:true},{account,records:new Map([[id(6),count]])});
 assert.equal(accepted.credit_application_id,id(2));assert.equal(accepted.credit_application_version,1);
 const {credit_application_version,...incomplete}=recorded;assert.throws(()=>validateSurplusCommand(incomplete));
 assert.throws(()=>buildSurplusCommand('collector_count_record',{...fields,credit_application_id:id(99)},{account,preview,records:new Map()}));
});
test('preview and count results reject silently ignored or changed credit',()=>{
 assert.equal(validateApplicationPreview(preview,approval),preview);
 assert.throws(()=>validateApplicationPreview({...preview,authorized_credit_application:'0.00'},approval));
 assert.throws(()=>validateApplicationPreview(preview));
 const body={action:'collector_count_record',credit_application_id:id(2),credit_application_version:1};
 const held={options:{body},reference:preview};
 validateApplicationResult({status:'saved',result:{count}},held);
 assert.throws(()=>validateApplicationResult({status:'saved',result:{count:{...count,credit_application_version:2}}},held));
});
