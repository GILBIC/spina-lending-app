import assert from 'node:assert/strict';
import test from 'node:test';
import { applicationSource } from '../assets/management-protected-accounting.js';

const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const scope = { bookId: id(1), accountId: id(2), applicationId: id(3) };
const line = (line_number, account_code, debit, credit) => ({ line_number, account_code, debit, credit, account_snapshot: { name: account_code } });
const source = (regular = true) => ({
  book_id: id(1), treasury_account_id: id(2), application_id: id(3), receipt_id: id(4), transaction_id: id(5),
  event_id: id(6), loan_id: id(7), fiscal_period_id: id(8), posting_date: '2026-09-30', source_digest: 'a'.repeat(64), amount: '200.00',
  product_model: regular ? 'fixed_daily' : 'seven_by_seven',
  accounting_policy_version: regular ? 'treasury_regular_original_first_cash_v1' : 'treasury_seven_by_seven_application_v1',
  lines: [line(1, '2200', '200.00', '0.00'), line(2, '1120', '62.58', '0.00'), line(3, regular ? '4000' : '4010', '0.00', '62.58'), line(4, '1120', '0.00', '62.58'), line(5, regular ? '1100' : '1110', '0.00', '137.42')],
  origin: { private: 'DO NOT DISPLAY' },
});

test('Regular application retains explicit product and policy with exact principal and interest', () => {
  const projected = applicationSource(source(), scope);
  assert.equal(projected.product_model, 'fixed_daily');
  assert.equal(projected.accounting_policy_version, 'treasury_regular_original_first_cash_v1');
  assert.equal(projected.lines[4].credit, '137.42');
  assert.ok(!JSON.stringify(projected).includes('DO NOT DISPLAY'));
});

for (const policy of ['treasury_regular_original_chronological_cash_v1', 'treasury_regular_renewal_chronological_cash_v1']) {
test(`${policy} permits no new interest and retains its policy`, () => {
  const value = { ...source(), accounting_policy_version: policy, lines: [line(10, '2200', '200.00', '0.00'), line(50, '1100', '0.00', '200.00')] };
  const projected = applicationSource(value, scope);
  assert.equal(projected.accounting_policy_version, value.accounting_policy_version);
  assert.equal(projected.lines.length, 2);
  assert.ok(!JSON.stringify(projected).includes('DO NOT DISPLAY'));
  assert.throws(() => applicationSource({ ...value, product_model: 'seven_by_seven' }, scope));
});
}

test('full payoff separates settlement gain from interest and requires retained treatment', () => {
  const value = { ...source(), accounting_policy_version: 'treasury_regular_original_full_payoff_v1',
    payoff: { payoff_review_id: id(9), payoff_treatment: 'full_contractual_payoff_no_rebate', contract_evidence_reference: 'SIGNED-1', payoff_review_rationale: 'Reviewed the actual complete contractual settlement.', gross_carrying_before: '180.00', settlement_difference: '20.00' },
    lines: [line(10, '2200', '200.00', '0.00'), line(50, '1100', '0.00', '180.00'), line(60, '4030', '0.00', '20.00')] };
  assert.equal(applicationSource(value, scope).payoff.payoff_review_id, id(9));
  assert.throws(() => applicationSource({ ...value, payoff: undefined }, scope));
  assert.throws(() => applicationSource({ ...value, accounting_policy_version: 'treasury_regular_original_chronological_cash_v1' }, scope));
  assert.throws(() => applicationSource({ ...value, payoff: { ...value.payoff, settlement_difference: '19.00' } }, scope));
  assert.ok(!JSON.stringify(applicationSource(value, scope)).includes('DO NOT DISPLAY'));
});

for (const mutation of ['policy', 'model', 'hybrid_principal', 'hybrid_income', 'missing_identity', 'duplicate_line', 'two_sided', 'income_without_accrual', 'duplicate_principal']) {
  test(`application refuses a balanced source with ${mutation}`, () => {
    const value = source(false);
    if (mutation === 'policy') value.accounting_policy_version = 'treasury_regular_original_first_cash_v1';
    if (mutation === 'model') value.product_model = 'fixed_daily';
    if (mutation === 'hybrid_principal') value.lines[4].account_code = '1100';
    if (mutation === 'hybrid_income') value.lines[2].account_code = '4000';
    if (mutation === 'missing_identity') delete value.product_model;
    if (mutation === 'duplicate_line') value.lines[4].line_number = 1;
    if (mutation === 'two_sided') { value.lines[1].debit = '63.58'; value.lines[1].credit = '1.00'; }
    if (mutation === 'income_without_accrual') value.lines = [value.lines[0], value.lines[2], value.lines[4]];
    if (mutation === 'duplicate_principal') value.lines = [value.lines[0], line(2, '1110', '0.00', '100.00'), line(3, '1110', '0.00', '100.00')];
    assert.throws(() => applicationSource(value, scope));
  });
}
