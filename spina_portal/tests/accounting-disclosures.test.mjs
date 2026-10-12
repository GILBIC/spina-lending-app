import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { reportingSupplementMarkup } from '../assets/accounting-reporting.js';

const url = new URL('../assets/accounting-disclosures.js', import.meta.url);
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const lines = () => [
  { id: uuid(1), account_code: '1598', account_name: 'Asset', debit: '1000.00', credit: '0.00', cash_allocations: null },
  { id: uuid(2), account_code: '1010', account_name: 'Cash', debit: '0.00', credit: '400.00', cash_allocations: [{ category: 'investing', amount: '-400.00' }] },
  { id: uuid(3), account_code: '2300', account_name: 'Borrowings', debit: '0.00', credit: '600.00', cash_allocations: null },
];
const parts = () => [{ debit_line_id: uuid(1), credit_line_id: uuid(2), amount: '400.00', classification: 'cash_investing', evidence_reference: 'Cash purchase', evidence_digest: 'a'.repeat(64) }, { debit_line_id: uuid(1), credit_line_id: uuid(3), amount: '600.00', classification: 'noncash_investing_financing', evidence_reference: 'Borrowing contract', evidence_digest: 'b'.repeat(64) }];
async function module() { assert.ok(existsSync(url), 'Mixed-journal disclosure client is not implemented'); return import(url); }

test('mixed allocation preserves exact cash and borrowing portions', async () => {
  const { disclosureComponents } = await module();
  assert.deepEqual(disclosureComponents(lines(), parts(), ['1010']), parts());
});
for (const change of [p => p.pop(), p => p.push(structuredClone(p[1])), p => p[1].amount = '600.001', p => p[1].amount = 600, p => p[1].amount = '-600.00', p => p[0].classification = 'noncash_investing', p => p[0].classification = 'cash_financing', p => p[1].debit_line_id = uuid(3)]) {
  test('invalid component cannot enter a retained review', async () => {
    const { disclosureComponents } = await module(); const values = parts(); change(values);
    assert.throws(() => disclosureComponents(lines(), values, ['1010']));
  });
}

test('remaining amounts show the exact unallocated line portion', async () => {
  const { disclosureRemaining } = await module();
  assert.deepEqual(disclosureRemaining(lines(), [parts()[0]]), { [uuid(1)]: '600.00', [uuid(2)]: '0.00', [uuid(3)]: '600.00' });
});

const contract = () => JSON.parse(readFileSync(new URL('./fixtures/journal-disclosures-backend.json', import.meta.url), 'utf8'));
function staleContract() {
  const value = contract(), journal = value.journals[0];
  journal.review_status = 'source_changed'; value.status = 'disclosure_review_required';
  value.coverage.reviewed_count = 0; value.coverage.blocked_count = 1;
  value.blockers = [{ journal_entry_id: journal.journal_entry_id, entry_number: journal.entry_number, reason: 'source_changed' }];
  value.noncash_components = [];
  for (const row of value.financing_liabilities) Object.assign(row, { cash_changes: null, noncash_changes: null, opening_adjustments: null, difference: null, reconciled: false });
  return value;
}
test('stale reviews remain readable but malformed retained portions are rejected', async () => {
  const { validateDisclosures } = await module(), value = staleContract();
  value.journals[0].lines[1].cash_allocations = null;
  assert.equal(validateDisclosures(value).coverage.blocked_count, 1);
  value.journals[0].components[0].debit_line_id = uuid(99);
  assert.throws(() => validateDisclosures(value));
});
test('actual backend report retains coverage and financing reconciliation', async () => {
  const { validateDisclosures, disclosureMarkup } = await module();
  assert.equal(validateDisclosures(contract()).status, 'complete_for_posted_ledger');
  assert.match(disclosureMarkup(contract()), /Noncash · investing and financing/);
});
for (const tamper of [r => r.coverage.reviewed_count++, r => r.noncash_components[0].amount = '601.00', r => r.financing_liabilities[0].closing_balance = '601.00', r => { r.financing_liabilities[0].cash_changes = '100.00'; r.financing_liabilities[0].noncash_changes = '500.00'; }, r => r.journals[0].components[0].amount = '399.00', r => r.journals[0].lines[1].cash_allocations[0].category = 'financing']) {
  test('altered backend totals or components are rejected', async () => {
    const { validateDisclosures } = await module(); const value = contract(); tamper(value); assert.throws(() => validateDisclosures(value));
  });
}

test('statement supplement presents full mixed coverage when supplied', () => {
  const value = { changes_in_equity: { opening_equity: '0.00', profit_or_loss: '0.00', closing_equity: '0.00', reconciliation_difference: '0.00', reconciled: true, other_equity_movements: [] }, cash_flows: { policy: null, status: 'cash_definition_required', opening_cash: null, closing_cash: null, net_cash_flow: null, reconciliation_difference: null, categories: {}, reconciled: false, cash_lines: [], unclassified_lines: [], unclassified_line_count: 0 }, notes: { status: 'reporting_policy_required', items: [] }, noncash_activity: [], comparative: null, journal_disclosures: contract() };
  assert.match(reportingSupplementMarkup(value), /Cash and noncash disclosure review/);
  assert.doesNotMatch(reportingSupplementMarkup(value), /This inventory excludes mixed/);
});
