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
