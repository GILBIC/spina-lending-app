import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {validateSurplusCommand, validateSurplusResult} from '../assets/collector-surplus-contract.js';
const fixture=JSON.parse(await readFile(new URL('./fixtures/collector-credit-backend.json',import.meta.url),'utf8'));
test('actual credit approval, count and acceptance responses satisfy the complete Portal contract',()=>{
  assert.equal(fixture.synthetic_only,true);
  assert.equal(fixture.examples.length,6);
  for(const e of fixture.examples){
    validateSurplusCommand(e.command);
    const held={options:{body:e.command},actor:e.actor,accountId:e.account_id,contextId:e.ledger_context_id,collectorId:e.collector_user_id,reference:e.reference};
    assert.equal(validateSurplusResult(e.response,held),e.response);
    if(e.command.action==='collector_count_accept') {
      for(const change of [r=>r.result.application_entry.amount='1.00',r=>r.result.settlement.physical_amount='1.00',r=>r.result.action_record.status='reserved',r=>r.result.count.credit_application.version++]) {
        const bad=structuredClone(e.response);change(bad);
        assert.throws(()=>validateSurplusResult(bad,held));
      }
    }
  }
});
