import assert from 'node:assert/strict';
import test from 'node:test';
import { mountManagementAccounting } from '../assets/management-accounting.js';
import { Element, fire } from './helpers/dom.mjs';

const base = '/api/v1/management/financial-accounting';
const period = '00000000-0000-4000-8000-000000000001';
const workbook = '00000000-0000-4000-8000-000000000002';
const journal = '00000000-0000-4000-8000-000000000003';
const manager = { user: { id: 'manager', role: 'Management', roles: ['management'] }, permissions: ['accounting.view', 'accounting.period.manage', 'accounting.cutover.manage', 'accounting.opening_balance.prepare', 'accounting.opening_balance.post', 'accounting.period.close.prepare', 'accounting.period.close.post', 'accounting.initial_capital.evidence.record', 'accounting.initial_capital.prepare', 'accounting.initial_capital.post', 'accounting.ecl.review'] };
const overview = { fiscal_periods: [{ period_id: period, label: 'September', start_date: '2026-09-01', end_date: '2026-09-30', status: 'open' }], accounts: [], period_management_enabled: true, notice: 'Authoritative overview' };
const wb = () => ({ management_enabled: true, notice: 'Evidence only', summary: { workbook_id: workbook, cutover_date: '2026-09-01', status: 'draft', ready_for_review: true, total_debit: '1234567890123456.78', total_credit: '1234567890123456.78' }, lines: [{ workbook_id: workbook, account_code: '1100', account_name: 'Cash', proposed_debit: '0.00', proposed_credit: null, verification_status: 'pending' }], measurement: { loans: [], summary: {}, notice: 'Measured by server' } });
const tick = () => new Promise((resolve) => setImmediate(resolve));
const value = (root, name, text) => { root.querySelector(`[name="${name}"]`).value = text; };
async function setup(extra = {}) {
  const root = new Element(); const calls = [];
  const controller = new AbortController();
  const api = { async request(path, options = {}) { calls.push({ path, ...options }); if (options.method) return extra.write ? extra.write(path, options) : { period: overview.fiscal_periods[0] }; return extra.read?.(path) ?? overview; } };
  const cleanup = await mountManagementAccounting({ root, api, session: manager, signal: controller.signal });
  return { root, calls, controller, cleanup, tab: async (name) => { fire(root.querySelector(`[data-accounting-tab="${name}"]`), 'click'); await tick(); } };
}

test('accounting requires Management plus view permission before reading private records', async () => {
  for (const session of [{ user: { role: 'Employee' }, permissions: manager.permissions }, { user: { role: 'Management' }, permissions: [] }]) {
    let requests = 0; const root = new Element();
    await mountManagementAccounting({ root, session, api: { request() { requests++; } } });
    assert.equal(requests, 0); assert.equal(root.querySelector('form'), null);
  }
});

test('new fiscal period requires review and one confirmed submission', async () => {
  let resolveWrite;
  const f = await setup({ write: () => new Promise((resolve) => { resolveWrite = resolve; }) });
  value(f.root, 'label', 'October 2026'); value(f.root, 'start_date', '2026-10-01'); value(f.root, 'end_date', '2026-10-31');
  fire(f.root.querySelector('[data-period-create]'), 'submit'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 0);
  const button = f.root.querySelector('[data-accounting-confirm]'); fire(button, 'click'); fire(button, 'click'); await tick();
  const writes = f.calls.filter((call) => call.method);
  assert.equal(writes.length, 1); assert.equal(writes[0].path, `${base}/fiscal-periods`);
  assert.deepEqual(writes[0].body, { label: 'October 2026', start_date: '2026-10-01', end_date: '2026-10-31' });
  assert.equal(writes[0].financial, true); resolveWrite({ period: overview.fiscal_periods[0] }); await tick(); f.cleanup();
});

test('opening line saves exact money and locks uncertain outcomes until reload', async () => {
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? wb() : overview, write: () => { throw new Error('Connection interrupted'); } });
  await f.tab('workbook');
  value(f.root, 'debit', '1234567890123456.78'); value(f.root, 'credit', ''); value(f.root, 'verification_status', 'verified'); value(f.root, 'evidence_note', 'Reviewed cash evidence');
  fire(f.root.querySelector('[data-workbook-line]'), 'submit'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const writes = f.calls.filter((call) => call.method);
  assert.deepEqual(writes[0].body, { debit: '1234567890123456.78', credit: null, verification_status: 'verified', evidence_note: 'Reviewed cash evidence' });
  assert.equal(writes[0].path, `${base}/opening-balance-workbook/${workbook}/lines/1100`);
  assert.match(f.root.textContent, /uncertain/i); assert.equal(f.root.querySelector('[data-accounting-confirm]'), null);
  fire(f.root.querySelector('[data-accounting-refresh]'), 'click'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 1); assert.ok(f.root.querySelector('[data-workbook-line]')); f.cleanup();
});

test('cancelled opening-line review returns to the entered draft and its first field', async () => {
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? wb() : overview });
  await f.tab('workbook');
  value(f.root, 'debit', '1234.56'); value(f.root, 'credit', '');
  value(f.root, 'verification_status', 'verified'); value(f.root, 'evidence_note', 'Reviewed cash evidence');
  fire(f.root.querySelector('[data-workbook-line]'), 'submit'); await tick();
  assert.match(f.root.textContent, /1,234\.56/);
  fire(f.root.querySelector('[data-accounting-cancel]'), 'click'); await tick();
  assert.equal(f.root.querySelector('[name="debit"]').value, '1234.56');
  assert.equal(f.root.querySelector('[name="credit"]').value, '');
  assert.equal(f.root.querySelector('[name="verification_status"]').value, 'verified');
  assert.equal(f.root.querySelector('[name="evidence_note"]').value, 'Reviewed cash evidence');
  assert.equal(f.root.querySelector('[name="debit"]').focused, true);
  assert.equal(f.calls.filter((call) => call.method).length, 0);
  f.cleanup();
});

test('confirmed rejected opening line keeps its draft without replaying the write', async () => {
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? wb() : overview,
    write: () => { throw Object.assign(new Error('Evidence note needs review.'), { status: 422 }); } });
  await f.tab('workbook');
  value(f.root, 'debit', '1234.56'); value(f.root, 'credit', '');
  value(f.root, 'verification_status', 'verified'); value(f.root, 'evidence_note', 'Reviewed cash evidence');
  fire(f.root.querySelector('[data-workbook-line]'), 'submit'); await tick();
  fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 1);
  assert.equal(f.root.querySelector('[name="debit"]').value, '1234.56');
  assert.equal(f.root.querySelector('[name="evidence_note"]').value, 'Reviewed cash evidence');
  assert.equal(f.root.querySelector('[name="debit"]').focused, true);
  assert.match(f.root.textContent, /Evidence note needs review/);
  assert.equal(f.root.querySelector('[data-accounting-confirm]'), null);
  value(f.root, 'evidence_note', 'Corrected retained evidence note');
  fire(f.root.querySelector('[data-workbook-line]'), 'submit'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 1);
  fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 2);
  f.cleanup();
});

test('cancelled policy review keeps the selected choice and note', async () => {
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? wb() : overview });
  await f.tab('workbook');
  value(f.root, 'confirmed', 'true'); value(f.root, 'policy_note', 'Approved company migration policy');
  fire(f.root.querySelector('[data-workbook-policy]'), 'submit'); await tick();
  fire(f.root.querySelector('[data-accounting-cancel]'), 'click'); await tick();
  assert.equal(f.root.querySelector('[name="confirmed"]').value, 'true');
  assert.equal(f.root.querySelector('[name="policy_note"]').value, 'Approved company migration policy');
  assert.equal(f.root.querySelector('[name="confirmed"]').focused, true);
  assert.equal(f.calls.filter((call) => call.method).length, 0);
  f.cleanup();
});

test('opening post binds the current journal identity and authoritative decimal totals', async () => {
  const draft = { workbook_id: workbook, cutover_date: '2026-09-01', workbook_status: 'review_ready', journal_entry_id: journal, journal_status: 'draft', draft_prepared: true, preparation_ready: false, opening_balance_posting_enabled: true, automatic_source_posting_enabled: false, posting_ready: true, total_debit: '1234567890123456.78', total_credit: '1234567890123456.78' };
  const f = await setup({ read: (path) => path.endsWith('journal-draft') ? { journal_draft: draft } : path.includes('opening-balance-workbook') ? wb() : overview, write: () => ({ journal_draft: { ...draft, journal_status: 'posted' } }) });
  await f.tab('opening'); fire(f.root.querySelector('[data-opening-post]'), 'click'); await tick();
  assert.match(f.root.textContent, /1,234,567,890,123,456\.78/);
  fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  assert.deepEqual(f.calls.find((call) => call.method).body, { confirm: true, journal_entry_id: journal, total_debit: '1234567890123456.78', total_credit: '1234567890123456.78' }); f.cleanup();
});

test('aborting a workspace removes private content and makes detached confirmation inert', async () => {
  const f = await setup();
  value(f.root, 'label', 'October'); value(f.root, 'start_date', '2026-10-01'); value(f.root, 'end_date', '2026-10-31');
  fire(f.root.querySelector('[data-period-create]'), 'submit'); await tick();
  const button = f.root.querySelector('[data-accounting-confirm]'); f.controller.abort(); fire(button, 'click'); await tick();
  assert.equal(f.root.innerHTML, ''); assert.equal(f.calls.filter((call) => call.method).length, 0);
});

test('period close posts the reviewed digest, signed income and period end with explicit confirmation', async () => {
  const item = { fiscal_period_id: period, label: 'September', end_date: '2026-09-30', fiscal_period_status: 'review', close_status: 'prepared_confirmation_required', close_digest: 'a'.repeat(64), net_income: '-123.45', protected_period_close_enabled: true, retained_earnings_close_enabled: true, closed_period_posting_protection_enabled: true, period_reopen_enabled: false, automatic_source_posting: false };
  Object.assign(item, { preparation_id: workbook, journal_entry_id: journal, temporary_account_count: 4, retained_earnings_balance_before: '12345.67' });
  const f = await setup({ read: (path) => path.endsWith('period-close') ? { items: [item], permissions: { close_prepare: true, close_post: true } } : overview, write: () => ({ item: { ...item, close_status: 'closed' } }) });
  await f.tab('close'); fire(f.root.querySelector('[data-close-post]'), 'click'); await tick();
  fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const write = f.calls.find((call) => call.method);
  assert.equal(write.path, `${base}/period-close/${period}/post`);
  assert.equal(write.body.expected_net_income, '-123.45'); assert.equal(write.body.expected_close_digest, 'a'.repeat(64));
  assert.equal(write.body.expected_period_end_date, '2026-09-30'); assert.equal(write.body.expected_retained_earnings_account_code, '3100');
  assert.match(write.body.confirmation_token, /^[0-9a-f]{64}$/); f.cleanup();
});

test('capital posting uses exact evidence coordinates and never invents a balancing journal', async () => {
  const item = { evidence_id: workbook, funding_date: '2026-09-01', amount: '90071992547409.93', cash_account_code: '1100', cash_account_name: 'Cash', evidence_digest: 'b'.repeat(64), evidence_reference: 'OWNER-001', evidence_note: 'Reviewed retained bank deposit evidence', fiscal_period_id: period, accounting_status: 'prepared_not_posted', protected_initial_capital_funding_enabled: true, synthetic_opening_balance_required: false, automatic_source_posting: false };
  Object.assign(item, { capital_account_code: '3000', journal_entry_id: journal, journal_status: 'draft', prepared_by_user_id: period, prepared_at: '2026-09-29T00:00:00Z' });
  const f = await setup({ read: (path) => path.includes('initial-capital-funding') ? { items: [item], cash_accounts: [], permissions: { post: true }, protected_initial_capital_funding_enabled: true, synthetic_opening_balance_required: false, automatic_source_posting: false } : overview, write: () => ({ item: { ...item, accounting_status: 'posted' } }) });
  await f.tab('capital'); fire(f.root.querySelector('[data-capital-post]'), 'click'); await tick();
  fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const write = f.calls.find((call) => call.method);
  assert.equal(write.body.expected_amount, '90071992547409.93'); assert.equal(write.body.expected_fiscal_period_id, period);
  assert.equal(write.body.expected_evidence_digest, 'b'.repeat(64)); assert.equal(write.body.expected_posting_date, '2026-09-01');
  assert.equal(write.path, `${base}/initial-capital-funding/${workbook}/post`); f.cleanup();
});

test('historical review records an explicit evidence-backed label and reloads its queue', async () => {
  const row = { historical_episode_id: 123, episode_key: 'H-123', borrower_key: 'CLIENT-123', principal: '123.45', source_quality_status: 'ready_for_outcome_labeling', review_status: 'outcome_review_required' };
  const f = await setup({ read: (path) => path.includes('ecl-outcome-review') ? { episodes: [row], review_permission: true } : overview, write: () => row });
  await f.tab('outcomes');
  value(f.root, 'default_label', 'false'); value(f.root, 'evidence_basis', 'collection_history'); value(f.root, 'evidence_reference', 'RETAINED-123'); value(f.root, 'review_note', 'Reviewed original payment records.');
  fire(f.root.querySelector('[data-outcome-review]'), 'submit'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  assert.deepEqual(f.calls.find((call) => call.method).body, { default_label: false, evidence_basis: 'collection_history', evidence_reference: 'RETAINED-123', review_note: 'Reviewed original payment records.' }); f.cleanup();
});

test('unknown protected policy flags never expose financial posting actions', async () => {
  const f = await setup({ read: (path) => path.endsWith('period-close') ? { items: [{ fiscal_period_id: period, close_status: 'prepared_confirmation_required' }], permissions: { close_post: true } } : overview });
  await f.tab('close'); assert.equal(f.root.querySelector('[data-close-post]'), null); f.cleanup();
});

test('accounting overview exposes source summaries, chart and cutover evidence without computed balances', async () => {
  const f = await setup({ read: () => ({ ...overview, summary: { active_loan_count: 3, active_principal: '9999999999999999.99', operational_outstanding: '123.45', unremitted_cash: '12.34' }, foundation: { posted_journal_count: 5 }, accounts: [{ code: '1100', name: 'Cash on hand', account_type: 'asset', normal_balance: 'debit', is_posting: true, is_active: true }], policies: [{ name: 'Regular loan', operational_rule: 'Contract installments', accounting_rule: 'Effective interest evidence', renewal_rule: 'Reviewed renewal' }], cutover: { summary: { overall_status: 'blocked' }, loans: [{ loan_number: 'L-123', client_name: 'Sample Client', readiness_status: 'contract_validation_required', blockers: ['Missing approved source contract'] }] } }) });
  assert.match(f.root.innerHTML, /9,999,999,999,999,999\.99/);
  assert.match(f.root.innerHTML, /Cash on hand/);
  assert.match(f.root.innerHTML, /Missing approved source contract/);
  assert.match(f.root.innerHTML, /Effective interest evidence/); f.cleanup();
});

test('period status changes do not bypass formal close', async () => {
  const f = await setup({ write: () => ({ period: { ...overview.fiscal_periods[0], status: 'review' } }) });
  fire(f.root.querySelector('[data-period-status]'), 'click'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const write = f.calls.find((call) => call.method); assert.equal(write.path, `${base}/fiscal-periods/${period}/status`); assert.deepEqual(write.body, { status: 'review', confirm_close: false }); f.cleanup();
});

test('workbook policy and readiness are separately confirmed evidence actions', async () => {
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? wb() : overview, write: () => wb() }); await f.tab('workbook');
  value(f.root, 'confirmed', 'true'); value(f.root, 'policy_note', 'Approved company migration policy'); fire(f.root.querySelector('[data-workbook-policy]'), 'submit'); await tick();
  assert.equal(f.calls.filter((call) => call.method).length, 0); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  fire(f.root.querySelector('[data-workbook-status]'), 'click'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const writes = f.calls.filter((call) => call.method); assert.deepEqual(writes[0].body, { confirmed: true, policy_note: 'Approved company migration policy' }); assert.equal(writes[0].method, 'PUT'); assert.equal(writes[0].path, `${base}/opening-balance-workbook/${workbook}/policy`); assert.deepEqual(writes[1].body, { status: 'review_ready' }); f.cleanup();
});

test('capital evidence uses exact cents and a fresh idempotency coordinate before journal preparation', async () => {
  const item = { evidence_id: workbook, amount: '1234567890123456.78', evidence_digest: 'b'.repeat(64) };
  const f = await setup({ read: (path) => path.includes('initial-capital-funding') ? { items: [], cash_accounts: [{ code: '1100', name: 'Cash' }], permissions: { evidence_record: true }, protected_initial_capital_funding_enabled: true, synthetic_opening_balance_required: false, automatic_source_posting: false } : overview, write: () => ({ item }) }); await f.tab('capital');
  for (const [name, text] of Object.entries({ funding_date: '2026-09-01', amount: item.amount, cash_account_code: '1100', evidence_source: 'Original bank document', evidence_reference: 'BANK-123', evidence_digest: item.evidence_digest, evidence_note: 'Retained bank deposit and approved reconciliation' })) value(f.root, name, text);
  fire(f.root.querySelector('[data-capital-evidence]'), 'submit'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const write = f.calls.find((call) => call.method); assert.equal(write.path, `${base}/initial-capital-funding/evidence`); assert.equal(write.body.amount, item.amount); assert.match(write.body.idempotency_key, /^[0-9a-f-]{36}$/); assert.equal(Object.hasOwn(write.body, 'journal_entry_id'), false); f.cleanup();
});

test('mismatched opening journal identity blocks posting', async () => {
  const f = await setup({ read: (path) => path.endsWith('journal-draft') ? { journal_draft: { workbook_id: period, posting_ready: true, opening_balance_posting_enabled: true, automatic_source_posting_enabled: false, journal_status: 'draft' } } : path.includes('opening-balance-workbook') ? wb() : overview }); await f.tab('opening');
  assert.equal(f.root.querySelector('[data-opening-post]'), null); assert.match(f.root.innerHTML, /does not match/); f.cleanup();
});

test('protected preparation actions only prepare the selected server record', async () => {
  const policy = { protected_period_close_enabled: true, retained_earnings_close_enabled: true, closed_period_posting_protection_enabled: true, period_reopen_enabled: false, automatic_source_posting: false };
  const capitalPolicy = { protected_initial_capital_funding_enabled: true, synthetic_opening_balance_required: false, automatic_source_posting: false };
  const close = { ...policy, fiscal_period_id: period, close_status: 'ready_to_prepare', label: 'September', end_date: '2026-09-30' };
  const capital = { ...capitalPolicy, evidence_id: workbook, capital_account_code: '3000', accounting_status: 'evidence_ready', amount: '123.45', evidence_reference: 'BANK-123' };
  const draft = { workbook_id: workbook, cutover_date: '2026-09-01', workbook_status: 'review_ready', preparation_ready: true, draft_prepared: false };
  const f = await setup({ read: (path) => path.endsWith('period-close') ? { items: [close], permissions: { close_prepare: true } } : path.includes('initial-capital-funding') ? { ...capitalPolicy, items: [capital], cash_accounts: [], permissions: { prepare: true } } : path.endsWith('journal-draft') ? { journal_draft: draft } : path.includes('opening-balance-workbook') ? wb() : overview, write: (path) => path.includes('period-close') ? { item: close } : path.includes('initial-capital-funding') ? { item: capital } : { journal_draft: draft } });
  for (const [tab, selector] of [['close', '[data-close-prepare]'], ['capital', '[data-capital-prepare]'], ['opening', '[data-opening-prepare]']]) {
    await f.tab(tab); fire(f.root.querySelector(selector), 'click'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  }
  const writes = f.calls.filter((call) => call.method);
  assert.deepEqual(writes.map((call) => call.path), [`${base}/period-close/${period}/prepare`, `${base}/initial-capital-funding/${workbook}/prepare`, `${base}/opening-balance-workbook/${workbook}/journal-draft`]);
  for (const write of writes) assert.deepEqual(write.body, { confirm: true }); f.cleanup();
});

test('workbook initialization confirms the chosen date and reloads created server identity', async () => {
  const empty = wb(); empty.summary.workbook_id = null; empty.summary.status = 'not_started'; empty.lines = [];
  const f = await setup({ read: (path) => path.includes('opening-balance-workbook') ? empty : overview, write: () => wb() }); await f.tab('workbook');
  value(f.root, 'cutover_date', '2026-09-01'); fire(f.root.querySelector('[data-workbook-create]'), 'submit'); await tick(); fire(f.root.querySelector('[data-accounting-confirm]'), 'click'); await tick();
  const write = f.calls.find((call) => call.method); assert.equal(write.path, `${base}/opening-balance-workbook`); assert.deepEqual(write.body, { cutover_date: '2026-09-01' }); assert.equal(f.calls.filter((call) => call.path === write.path && !call.method).length, 2); f.cleanup();
});
