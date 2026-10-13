import assert from 'node:assert/strict';
import test from 'node:test';
import { cashAllocations, reportingSupplementMarkup } from '../assets/accounting-reporting.js';
import { mountManagementSourceAccounting } from '../assets/management-source-accounting.js';
import { Element, fire } from './helpers/dom.mjs';

test('cash allocations preserve signed exact cents and must cover the whole cash line', () => {
  assert.deepEqual(cashAllocations([{ category: 'operating', amount: '-40.00' }, { category: 'financing', amount: '-60.00' }], '-100.00'), [{ category: 'operating', amount: '-40.00' }, { category: 'financing', amount: '-60.00' }]);
  assert.throws(() => cashAllocations([{ category: 'operating', amount: '100.00' }], '-100.00'));
  assert.throws(() => cashAllocations([{ category: 'operating', amount: '-90.00' }], '-100.00'));
  assert.throws(() => cashAllocations([{ category: 'operating', amount: '-100.001' }], '-100.00'));
});

export const supplement = () => ({ changes_in_equity: { opening_equity: '90071992547409.93', profit_or_loss: '10.00', other_equity_movements: [], closing_equity: '90071992547419.93', reconciliation_difference: '0.00', reconciled: true }, cash_flows: { policy: null, status: 'cash_definition_required', opening_cash: null, closing_cash: null, net_cash_flow: null, reconciliation_difference: null, categories: {}, reconciled: false, cash_lines: [], unclassified_lines: [], unclassified_line_count: 0 }, notes: { status: 'reporting_policy_required', items: [], framework_label: null }, noncash_activity: [], comparative: null });

test('unconfigured cash reports show unavailable rather than manufactured zeros', () => {
  const markup = reportingSupplementMarkup(supplement());
  assert.match(markup, /Statement of Changes in Equity/); assert.match(markup, /90,071,992,547,409\.93/);
  assert.match(markup, /Cash definition required/i); assert.match(markup, /Opening cash.*Unavailable/);
  assert.match(markup, /No comparative period returned/);
  assert.match(markup, /posted ledger only/i);
});

test('missing supplemental evidence does not claim complete reporting', () => {
  assert.match(reportingSupplementMarkup(null), /Additional report evidence is unavailable/);
  assert.match(reportingSupplementMarkup({}), /Additional report evidence is incomplete/);
});

test('changed cash definition shows unavailable totals and requires a new policy', async () => {
  const supplemental = supplement();
  supplemental.cash_flows = { ...supplemental.cash_flows, status: 'cash_definition_changed', policy: { id: uuid(4), book_id: book.book_id, fiscal_period_id: uuid(3), version: 2, cash_definition_valid: false, cash_account_codes: ['1010'] } };
  const markup = reportingSupplementMarkup(supplemental);
  assert.match(markup, /Cash definition changed; review a new policy\./);
  assert.match(markup, /Net cash flow<\/dt><dd>Unavailable/);
  const root = new Element(), api = fixture(supplemental);
  await mountManagementSourceAccounting({ root, api, session, mode: 'reporting' });
  assert.ok(root.querySelector('[data-report-policy]'));
  assert.equal(root.querySelector('[data-report-classify]'), null);
  assert.equal(api.writes.length, 0);
  supplemental.cash_flows.net_cash_flow = '0.00';
  assert.match(reportingSupplementMarkup(supplemental), /evidence is incomplete/);
});

const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const digest = 'a'.repeat(64), tick = () => new Promise((resolve) => setImmediate(resolve));
const book = { status: 'configured', book_id: uuid(1), kind: 'owner_operations', entity_label: 'Owner operations' };
const session = { user: { id: uuid(2), role: 'Management', roles: ['management'] }, permissions: ['accounting.view', 'accounting.journal.manage'] };
function fixture(supplemental = supplement()) { const writes = []; return { writes, async request(path, options = {}) { if (options.method === 'POST') { writes.push(structuredClone(options.body)); return { policy_id: uuid(4), classification_id: uuid(5) }; } if (path.endsWith('/book')) return { book }; if (path.includes('/reporting-policy?')) return { policy: supplemental.cash_flows.policy }; if (path.includes('/statements?')) return { statements: { period: { period_id: uuid(3) }, reporting_supplement: supplemental } }; return { fiscal_periods: [{ period_id: uuid(3), label: 'September' }] }; } }; }

test('reporting policy requires actual cash choices and retained notes before an explicit save', async () => {
  const root = new Element(), api = fixture();
  await mountManagementSourceAccounting({ root, api, session, mode: 'reporting' }); fire(root.querySelector('[data-report-policy]'), 'click');
  const form = root.querySelector('[data-report-policy-form]');
  for (const [key, value] of Object.entries({ framework_label: 'Actual reporting basis', cash_1010: 'yes', cash_1020: 'no', cash_1030: 'yes', evidence_reference: 'Policy record', evidence_digest: digest, note_0_title: 'Borrowing terms', note_0_text: 'Actual retained terms.', note_0_evidence_reference: 'Agreement A', note_0_evidence_digest: digest })) form.querySelector(`[name="${key}"]`).value = value;
  fire(form, 'submit'); await tick(); assert.equal(api.writes.length, 0); assert.match(root.textContent, /Actual retained terms/);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(api.writes.length, 1); assert.deepEqual(api.writes[0].cash_account_codes, ['1010', '1030']); assert.equal(api.writes[0].expected_version, 0); assert.equal(api.writes[0].notes[0].evidence_reference, 'Agreement A'); assert.equal(api.writes[0].reviewed, true);
});

test('cash classification reviews exact signed splits and binds the current policy and line version', async () => {
  const supplemental = supplement(); supplemental.cash_flows = { ...supplemental.cash_flows, status: 'classification_required', policy: { id: uuid(4), book_id: book.book_id, fiscal_period_id: uuid(3), version: 2, cash_definition_valid: true, cash_account_codes: ['1010'] }, opening_cash: '200.00', closing_cash: '100.00', opening_balance_adjustments: '0.00', categories: Object.fromEntries(['operating', 'investing', 'financing'].map((category) => [category, { receipts: '0.00', payments: '0.00', net: '0.00' }])), cash_lines: [{ journal_line_id: uuid(6), journal_entry_id: uuid(7), account_code: '1010', amount: '-100.00', entry_number: 'GJ-7', source_type: 'manual', is_opening_adjustment: false, classification_version: 3, allocations: null }] };
  const root = new Element(), api = fixture(supplemental); await mountManagementSourceAccounting({ root, api, session, mode: 'reporting' }); fire(root.querySelector('[data-report-classify]'), 'click');
  fire(root.querySelector('[data-add-allocation]'), 'click');
  const form = root.querySelector('[data-report-classification-form]');
  for (const [key, value] of Object.entries({ allocation_0_category: 'operating', allocation_0_amount: '-40.00', allocation_1_category: 'financing', allocation_1_amount: '-60.00', evidence_reference: 'Cash evidence', evidence_digest: digest })) form.querySelector(`[name="${key}"]`).value = value;
  fire(form, 'submit'); await tick(); assert.equal(api.writes.length, 0);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(api.writes[0].policy_id, uuid(4)); assert.equal(api.writes[0].journal_line_id, uuid(6)); assert.equal(api.writes[0].expected_version, 3); assert.equal(api.writes[0].expected_amount, '-100.00'); assert.equal(api.writes[0].allocations.length, 2);
});

test('protected opening reversals never offer cash flow classification', async () => {
  const supplemental = supplement();
  supplemental.cash_flows = { ...supplemental.cash_flows, status: 'complete_for_posted_ledger', policy: { id: uuid(4), book_id: book.book_id, fiscal_period_id: uuid(3), version: 2, cash_definition_valid: true, cash_account_codes: ['1010'] }, opening_cash: '100.00', closing_cash: '0.00', opening_balance_adjustments: '-100.00', net_cash_flow: '0.00', reconciliation_difference: '0.00', reconciled: true, categories: Object.fromEntries(['operating', 'investing', 'financing'].map((category) => [category, { receipts: '0.00', payments: '0.00', net: '0.00' }])), cash_lines: [{ journal_line_id: uuid(6), journal_entry_id: uuid(7), account_code: '1010', amount: '-100.00', entry_number: 'GJ-7', source_type: 'reversal', is_opening_adjustment: true, classification_version: 0, allocations: null }] };
  const root = new Element(), api = fixture(supplemental);
  await mountManagementSourceAccounting({ root, api, session, mode: 'reporting' });
  assert.match(root.textContent, /Opening balance adjustment/);
  assert.equal(root.querySelector('[data-report-classify]'), null);
  assert.equal(api.writes.length, 0);
});
