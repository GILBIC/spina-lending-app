import {loanPayoutSchemas} from './loan-payout-schemas.js';
const id = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const fail = () => {throw Error('The loan payout record is incomplete or does not match this review.');};
export const loanPayoutActions = new Set(Object.values(loanPayoutSchemas).map(s => s.properties.action.const));
export function payoutMoney(value) {
 if(typeof value !== 'string' || !/^(0|[1-9][0-9]{0,15})\.[0-9]{2}$/.test(value) || value === '0.00') fail();
 return value;
}
function field(schema, value) {
 if(schema.anyOf){if(!schema.anyOf.some(s=>{try{field(s,value);return true;}catch{return false;}}))fail();return;}
 if(schema.const!==undefined && value!==schema.const || schema.enum && !schema.enum.includes(value))fail();
 if(schema.type==='null'){if(value!==null)fail();return;}
 if(schema.type==='boolean'){if(typeof value!=='boolean')fail();return;}
 if(schema.type==='integer'){if(!Number.isSafeInteger(value)||value<(schema.minimum??-Infinity))fail();return;}
 if(schema.type==='string'){
  if(typeof value!=='string'||value.trim().length<(schema.minLength??0)||value.length>(schema.maxLength??Infinity))fail();
  if(schema.pattern&&!new RegExp(schema.pattern).test(value)||schema.format==='uuid'&&!id(value)||schema.format==='date-time'&&(!/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)||!Number.isFinite(Date.parse(value))))fail();
 }
}
export function validateLoanPayoutCommand(body) {
 const schema=Object.values(loanPayoutSchemas).find(s=>s.properties.action.const===body?.action);
 if(!schema||Object.keys(body).some(k=>!Object.hasOwn(schema.properties,k))||schema.required.some(k=>body[k]===undefined))fail();
 for(const [key,value] of Object.entries(body))field(schema.properties[key],value);
 if(body.reviewed_amount!==undefined)payoutMoney(body.reviewed_amount);
 if(body.action==='loan_payout_prepare'){
  if(body.source_kind==='first_loan'&&['authorization_id','packet_hash','contract_evidence_reference'].some(k=>!body[k]))fail();
  if(body.source_kind==='renewal'&&['authorization_id','packet_hash','contract_evidence_reference'].some(k=>body[k]!=null))fail();
 }
 return body;
}
export function validateLoanPayoutRow(row,{own=false}={}) {
 if(!object(row)||!id(row.id)||!Number.isSafeInteger(row.version)||row.version<1||!['first_loan','renewal'].includes(row.source_kind)||!['collector','borrower'].includes(row.destination)||!['prepared','debited','recipient_confirmed','completed','cancelled'].includes(row.status))fail();
 payoutMoney(row.amount);
 if(own){
  const allowed=['id','version','source_kind','status','amount','destination','label','acknowledgments','borrower_handover_status','account_id','ledger_context_id','blocker','stages','funding_method'];
  if(Object.keys(row).some(k=>!allowed.includes(k)))fail();
  if(row.acknowledgments!==undefined){
   if(!object(row.acknowledgments))fail();
   for(const [stage,ack] of Object.entries(row.acknowledgments)){
    if(!['recipient','borrower_handover','borrower'].includes(stage)||!object(ack)||Object.keys(ack).some(k=>!['received','reviewed_amount','receipt_method','acknowledged_at'].includes(k))||typeof ack.received!=='boolean'||!['cash','gcash','bank'].includes(ack.receipt_method)||!Number.isFinite(Date.parse(ack.acknowledged_at)))fail();
    payoutMoney(ack.reviewed_amount);
   }
  }
 }
 return row;
}
export function loanPayoutPreparation(account,source,recipientReference,destination='collector') {
 if(!source||!id(account?.id)||!Number.isSafeInteger(account.version)||account.version<1||!id(source.source_id)||!['first_loan','renewal'].includes(source.source_kind)||!['collector','borrower'].includes(destination)||!recipientReference?.trim())fail();
 if(source.source_kind==='first_loan'&&(!id(source.authorization_id)||!/^([a-f0-9]{64})$/.test(source.packet_hash)||!/^office-evidence:[a-f0-9-]+$/i.test(source.contract_evidence_reference)))fail();
 return {account_id:account.id,expected_version:account.version,source_kind:source.source_kind,source_id:source.source_id,destination,recipient_reference:recipientReference.trim(),...(source.source_kind==='first_loan'?{authorization_id:source.authorization_id,packet_hash:source.packet_hash,contract_evidence_reference:source.contract_evidence_reference}:{})};
}
export function validateLoanPayoutOutcome(value,held) {
 const body=held.options.body,row=validateLoanPayoutRow(value?.result?.payout,{own:body.action==='loan_payout_acknowledge'}),prior=held.payoutReference;
 if(row.id!==value.target_id||row.version!==value.version)fail();
 if(body.action==='loan_payout_prepare') {
  const preview=held.payoutPreview;
  if(!preview||row.status!=='prepared'||row.version!==1||row.source_id!==body.source_id||row.source_kind!==body.source_kind||row.destination!==body.destination||row.amount!==preview.amount||row.source_digest!==body.source_digest||row.recipient_reference!==body.recipient_reference)fail();
 } else {
  if(!prior||row.id!==prior.id||row.version!==body.payout_version+1||row.amount!==prior.amount||row.destination!==prior.destination||row.source_kind!==prior.source_kind)fail();
  const status=body.action==='loan_payout_cancel'?'cancelled':body.action.endsWith('_complete')?'completed':body.action==='loan_payout_recipient_confirm'?(body.received?'recipient_confirmed':'debited'):prior.status;
  if(row.status!==status)fail();
  const sameTime=(a,b)=>Number.isFinite(Date.parse(a))&&Date.parse(a)===Date.parse(b);
  if(body.action==='loan_payout_acknowledge'){
   const ack=row.acknowledgments?.[body.stage];
   if(value.result.stage!==body.stage||!ack||ack.received!==body.received||ack.reviewed_amount!==body.reviewed_amount||ack.receipt_method!==body.receipt_method||!sameTime(ack.acknowledged_at,body.acknowledged_at))fail();
  }else{
   if(['source_id','client_id','account_id','ledger_context_id','source_digest','recipient_reference'].some(k=>prior[k]!==undefined&&row[k]!==prior[k]))fail();
   if(body.action==='loan_payout_cancel'&&row.payload?.reason!==body.reason)fail();
   if(body.action==='loan_payout_recipient_confirm'){
    const ack=row.payload?.recipient_confirmation;
    if(!ack||ack.evidence_id!==body.evidence_id||ack.received!==body.received||ack.reviewed_amount!==body.reviewed_amount||ack.attestation!==body.recipient_attestation||!sameTime(ack.acknowledged_at,body.acknowledged_at))fail();
   }
   if(body.action==='loan_payout_first_loan_complete'){
    const receipt=row.payload?.borrower_receipt,ack=receipt?.snapshot;
    if(receipt?.evidence_id!==body.evidence_id||!ack||ack.amount!==body.reviewed_amount||ack.receipt_method!==body.receipt_method||ack.attestation!==body.borrower_attestation||!sameTime(ack.acknowledged_at,body.acknowledged_at))fail();
   }
   if(body.action==='loan_payout_renewal_complete'&&(row.payload?.proof_review?.evidence_id!==body.evidence_id||row.payload?.proof_review?.reason!==body.reason))fail();
  }
 }
 return value;
}
