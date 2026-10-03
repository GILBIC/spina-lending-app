import test from 'node:test';
import assert from 'node:assert/strict';
const contracts = await import('../assets/loan-payout-contract.js').catch(() => ({}));
const account='10000000-0000-4000-8000-000000000001', id='20000000-0000-4000-8000-000000000001', source='30000000-0000-4000-8000-000000000001';
const row = {id, version:2, status:'debited', source_kind:'first_loan', source_id:source, destination:'collector', amount:'1000.00', account_id:account, ledger_context_id:source};
test('loan payout rows reject invalid net amounts, destinations and missing identity',()=>{
 assert.equal(typeof contracts.validateLoanPayoutRow,'function');
 assert.equal(contracts.validateLoanPayoutRow(row).destination,'collector');
 for(const change of [{amount:1000},{amount:'0.00'},{destination:'other'},{version:0},{id:'untrusted'},{status:'paid'}])assert.throws(()=>contracts.validateLoanPayoutRow({...row,...change}));
});
test('own payout projection rejects private source and beneficiary metadata',()=>{
 assert.equal(typeof contracts.validateLoanPayoutRow,'function');
 const {source_id,...own}=row;contracts.validateLoanPayoutRow(own,{own:true});
 for(const field of ['recipient_reference','source_snapshot','evidence_id','source_receipt'])assert.throws(()=>contracts.validateLoanPayoutRow({...row,[field]:'private'},{own:true}));
});
test('preparation defaults to Collector at the consumer boundary and binds an explicit source',()=>{
 assert.equal(typeof contracts.loanPayoutPreparation,'function');
 const item={source_kind:'first_loan',source_id:source,packet_hash:'a'.repeat(64),authorization_id:id,contract_evidence_reference:'office-evidence:'+id};
 const input=contracts.loanPayoutPreparation({id:account,version:1},item,'Actual collector destination');
 assert.equal(input.destination,'collector');
 assert.equal(contracts.loanPayoutPreparation({id:account,version:1},item,'Actual borrower destination','borrower').destination,'borrower');
 assert.throws(()=>contracts.loanPayoutPreparation({id:account,version:1},null,'destination'));
});

test('own receipts reject nested private metadata and response must confirm the submitted acknowledgment',()=>{
 const prior={id,version:3,source_kind:'renewal',status:'recipient_confirmed',destination:'borrower',amount:'1000.00'};
 const body={action:'loan_payout_acknowledge',payout_id:id,payout_version:3,stage:'borrower',received:true,reviewed_amount:'1000.00',receipt_method:'gcash',acknowledged_at:'2026-10-03T04:00:00Z'};
 const ack={received:true,reviewed_amount:'1000.00',receipt_method:'gcash',acknowledged_at:'2026-10-03T04:00:00+00:00'};
 const held={payoutReference:prior,options:{body}};
 const saved={target_id:id,version:4,result:{stage:'borrower',payout:{...prior,version:4,acknowledgments:{borrower:ack}}}};
 contracts.validateLoanPayoutOutcome(saved,held);
 for(const change of [{received:false},{receipt_method:'cash'},{reviewed_amount:'999.00'},{acknowledged_at:'2026-10-02T04:00:00Z'},{wallet:{reference:'private'}}])assert.throws(()=>contracts.validateLoanPayoutOutcome({...saved,result:{...saved.result,payout:{...saved.result.payout,acknowledgments:{borrower:{...ack,...change}}}}},held));
});
