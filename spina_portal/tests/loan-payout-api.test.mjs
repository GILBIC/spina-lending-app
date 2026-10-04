import test from 'node:test';
import assert from 'node:assert/strict';
import {createTreasuryClient} from '../assets/treasury-api.js';
import {loanPayoutPreparation} from '../assets/loan-payout-contract.js';
const a='10000000-0000-4000-8000-000000000001',p='20000000-0000-4000-8000-000000000001',s='30000000-0000-4000-8000-000000000001',r='40000000-0000-4000-8000-000000000001';
const actor={user_id:s,device_id:r};
const account={id:a,version:1,ledger_context_id:s,kind:'gcash',actions:['loan_payout_prepare','loan_payout_recipient_confirm'],balance:null};
const w={contract_version:1,actor,enabled:true,owner_configured:true,capabilities:{},claims:[],blockers:[],accounts:[account]};
const source={source_kind:'first_loan',source_id:s,packet_hash:'b'.repeat(64),authorization_id:r,contract_evidence_reference:'office-evidence:'+r};
const input=loanPayoutPreparation(account,source,'Reviewed Collector wallet');
const preview={contract_version:1,actor,ledger_context_id:s,account_id:a,account_version:1,...input,amount:'1000.00',payee_id:r,client_id:s,collector_user_id:r,source_digest:'a'.repeat(64)};
const row={...input,id:p,version:1,status:'prepared',amount:'1000.00',source_digest:preview.source_digest,ledger_context_id:s};
const body={...input,action:'loan_payout_prepare',request_id:r,source_digest:preview.source_digest};
const result={contract_version:1,action:body.action,request_id:r,target_id:p,version:1,status:'saved',result:{actor_user_id:s,device_id:r,account_id:a,ledger_context_id:s,payout:row}};
const session=()=>({user:{id:s,role:'management',status:'active'},device_id:r,device_registered:true,permissions:['treasury.disbursement.record']});
function client(responder){return createTreasuryClient({request:async(path,options)=>path.endsWith('/workspace')?w:path.endsWith('/loan-payout-preview')?preview:responder(path,options)},{getSession:session});}
test('payout preparation requires the unchanged server preview and recovers one exact request',async()=>{
 let uncertain=true,posts=0;const c=client(async(path)=>{if(path.includes('/requests/'))return result;posts++;if(uncertain)throw Object.assign(Error('Lost response'),{code:'network_uncertain'});return result;});
 await c.workspace();assert.equal(typeof c.loanPayoutPreview,'function');await c.loanPayoutPreview(input);
 await assert.rejects(c.execute({...body,destination:'borrower'}));assert.equal(posts,0);
 await assert.rejects(c.execute(body));assert.equal(c.state().status,'uncertain');
 assert.deepEqual(await c.recover(),result);assert.equal(posts,1);c.dispose();
});
test('a mismatched payout amount or destination never unlocks an uncertain submission',async()=>{
 for(const change of [{amount:'999.00'},{destination:'borrower'},{source_id:r}]){
  const c=client(async()=>({...result,result:{...result.result,payout:{...row,...change}}}));await c.workspace();assert.equal(typeof c.loanPayoutPreview,'function');await c.loanPayoutPreview(input);
  await assert.rejects(c.execute(body),error=>error.code==='treasury_result_unverified');assert.equal(c.state().status,'uncertain');c.dispose();
 }
});
