import assert from 'node:assert/strict';
import test from 'node:test';
import * as review from '../assets/remittance-review.js';
const actorId='11111111-1111-4111-8111-111111111111';
const record={remittance_id:'22222222-2222-4222-8222-222222222222',collector_user_id:'33333333-3333-4333-8333-333333333333',recipient_user_id:actorId,status:'submitted'};
test('reject requires exact recipient review and a bounded reason, without claiming physical receipt',()=>{
 const action=review.buildRemittanceRejection({record,actorId,reason:' Cash differs ',reviewed:true});
 assert.equal(action.path,`/api/v1/remittances/${record.remittance_id}/reject`);
 assert.deepEqual(action.options,{method:'POST',body:{review_acknowledged:true,reason:'Cash differs'},financial:true});
 for(const change of [{actorId:record.collector_user_id},{reviewed:false},{reason:' '},{reason:'x'.repeat(501)},{record:{...record,status:'received'}}])assert.throws(()=>review.buildRemittanceRejection({record,actorId,reason:'Cash differs',reviewed:true,...change}));
});
test('rejection uses exact remittance response, never the acceptance notification projection',()=>{
 const result={...record,status:'rejected',rejected_by_user_id:actorId,rejected_at:'2026-10-02T08:00:00Z',rejection_reason:'Cash differs'};
 assert.equal(review.rejectedRemittanceMatches(result,record,actorId,'Cash differs'),true);
 for(const change of [{remittance_id:record.collector_user_id},{collector_user_id:actorId},{status:'received'},{rejection_reason:'Other'},{rejected_by_user_id:record.collector_user_id},{rejected_at:null}])assert.equal(review.rejectedRemittanceMatches({...result,...change},record,actorId,'Cash differs'),false);
 assert.equal(review.rejectedRemittanceMatches({notification:result},record,actorId,'Cash differs'),false);
});
