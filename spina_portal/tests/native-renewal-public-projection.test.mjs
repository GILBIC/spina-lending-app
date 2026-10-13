import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { payoutSource, renewalCandidate } from '../assets/management-payout-accounting.js';
import { currentRiskContext } from '../assets/management-elapsed-assessments.js';

for (const [name, stage] of [['inherited-risk-context', 'stage_3_credit_impaired'], ['inherited-stage-two-context', 'stage_2_lifetime']]) test(`actual protected ${stage} context keeps predecessor history separate`, () => {
  const raw = JSON.parse(fs.readFileSync(new URL(`./fixtures/native-renewal-${name}.json`, import.meta.url), 'utf8'));
  const context = currentRiskContext(raw, {bookId: raw.book_id, periodId: raw.period_id, loanId: raw.loan_id});
  assert.equal(context.ready, true);
  assert.equal(context.prior_review, null);
  assert.deepEqual(context.inherited_review, raw.inherited_review);
  assert.notEqual(context.inherited_review.loan_id, context.loan_id);
  assert.equal(context.inherited_review.stage_label, stage);
  assert.equal(Object.hasOwn(context, 'credit_impaired_interest'), false);
  assert.equal(context.source_digest, raw.source_digest);
});

for (const name of ['modification_no_derecognition', 'derecognition', 'impaired-modification']) test(`genuine synthetic PG ${name} public candidate and completion`, () => {
  const raw = JSON.parse(fs.readFileSync(new URL(`./fixtures/native-renewal-${name}.json`, import.meta.url), 'utf8'));
  const scope = {bookId: raw.candidate.book_id, accountId: raw.candidate.treasury_account_id, payoutId: raw.candidate.payout_id};
  const candidate = renewalCandidate(raw.candidate, scope);
  const completion = payoutSource(raw.completion, {...scope, stage: 'completion'});
  assert.equal(candidate.new_loan_id, completion.loan_id);
  const treatment = name === 'impaired-modification' ? 'modification_no_derecognition' : name;
  assert.equal(completion.renewal_decision, treatment);
  assert.equal(completion.measurement.accounting_asset_continues, treatment === 'modification_no_derecognition');
  if (name !== 'impaired-modification') return;
  assert.equal(candidate.predecessor_credit_impaired, true);
  assert.equal(candidate.derecognition_blocker, 'successor_credit_adjusted_eir_policy_required');
  assert.equal(completion.predecessor_credit_impaired, true);
  assert.equal(completion.renewal_decision, 'modification_no_derecognition');
  assert.equal(completion.measurement.accounting_asset_continues, true);
  // This current-date protected lifecycle has no aged unwind or adjustment.
  assert.deepEqual(completion.credit_impaired_boundary, {
    allowance_before: '0.00', allowance_unwind: '0.00',
    impairment_adjustment: '0.00', allowance_after: '0.00',
  });
});
