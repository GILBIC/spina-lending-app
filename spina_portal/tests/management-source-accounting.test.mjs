import assert from 'node:assert/strict';
import test from 'node:test';
import { createSourceAccountingClient, receiptSource, liabilitySchedule, mountManagementSourceAccounting } from '../assets/management-source-accounting.js';
import { Element, fire } from './helpers/dom.mjs';

const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const base = '/api/v1/management/financial-accounting';
const session = { user: { id: uuid(1), role: 'Management', roles: ['management'] }, permissions: ['accounting.view', 'accounting.journal.manage', 'treasury.view', 'treasury.account.manage'] };
const book = { status: 'configured', book_id: uuid(2), kind: 'owner_operations', entity_label: 'Owner operations' };
const digest = 'a'.repeat(64);
const tick = () => new Promise((resolve) => setImmediate(resolve));
const source = () => ({ book_id: book.book_id, treasury_account_id: uuid(3), receipt_id: uuid(4), event_id: uuid(5), mapping_id: uuid(6), source_digest: digest, amount: '90071992547409.93', posting_date: '2026-09-30', fiscal_period_id: uuid(7), mapping: { cash_snapshot: { code: '1030', name: 'Cash - Bank / GCash' }, liability_snapshot: { code: '2200', name: 'Unapplied Borrower Funds' } }, receipt: { reference: 'Private <receipt>' }, evidence: { sha256: digest } });
const scope = { bookId: book.book_id, accountId: uuid(3), receiptId: uuid(4), mappingId: uuid(6) };
const schedule = () => ({ book, as_of: '2026-09-30', obligations: [], movements: [], reconciliation: [], unregistered_lines: [], registered_controls_reconciled: false, comprehensive_source_coverage: false });

test('receipt review rejects another scope and preserves exact money', () => {
  assert.equal(receiptSource(source(), scope).amount, '90071992547409.93');
  assert.throws(() => receiptSource({ ...source(), amount: 100 }, scope));
  assert.throws(() => receiptSource({ ...source(), treasury_account_id: uuid(8) }, scope));
  assert.throws(() => receiptSource({ ...source(), book_id: uuid(8) }, scope));
});

test('uncertain writes retain the exact request and block a different action', async () => {
  const calls = []; let fail = true;
  const client = createSourceAccountingClient({ api: { async request(path, options) { calls.push({ path, body: structuredClone(options.body) }); if (fail) throw Error('Connection lost'); return { obligation_id: uuid(9) }; } }, session });
  const body = { request_id: uuid(10), evidence_reference: 'Invoice A' };
  await assert.rejects(client.submit('/liabilities', body, (value) => value.obligation_id === uuid(9)));
  body.evidence_reference = 'Changed';
  await assert.rejects(client.submit('/liabilities', body, () => true), /unchanged request/);
  fail = false; await client.retry();
  assert.deepEqual(calls[0], calls[1]); assert.equal(calls.length, 2);
  assert.equal(client.pending(), false);
});

test('authorization loss clears an uncertain request and late data', async () => {
  const controller = new AbortController(); let finish;
  const client = createSourceAccountingClient({ api: { request() { return new Promise((resolve) => { finish = resolve; }); } }, session, signal: controller.signal });
  const promise = client.get('/liabilities'); controller.abort(); finish(schedule());
  await assert.rejects(promise, /Access changed/); assert.equal(client.pending(), false);
});

test('liability read requires complete partial-coverage evidence', () => {
  assert.equal(liabilitySchedule(schedule(), book.book_id).as_of, '2026-09-30');
  assert.throws(() => liabilitySchedule({ ...schedule(), unregistered_lines: null }, book.book_id));
  assert.throws(() => liabilitySchedule({ ...schedule(), comprehensive_source_coverage: true }, book.book_id));
});

test('liability registration reviews the returned line before writing and retries identical evidence', async () => {
  const data = schedule(); data.unregistered_lines = [{ journal_line_id: uuid(11), journal_entry_id: uuid(12), entry_number: 'GJ-1', account_code: '2300', posting_date: '2026-09-30', debit: '0.00', credit: '100.00', source_type: 'manual', source_reference: null, reversal_of_entry_id: null }];
  const calls = []; let fail = true; const root = new Element();
  const dispose = await mountManagementSourceAccounting({ root, session, mode: 'liabilities', api: { async request(path, options = {}) { calls.push({ path, options }); if (path.endsWith('/book')) return { book }; if (options.method === 'POST') { if (fail) throw Error('Lost'); return { obligation_id: uuid(13) }; } return data; } } });
  fire(root.querySelector('[data-register-line]'), 'click');
  const form = root.querySelector('[data-liability-form]');
  for (const [name, value] of Object.entries({ counterparty: 'Lender <A>', evidence_reference: 'Agreement 1', evidence_digest: digest })) form.querySelector(`[name="${name}"]`).value = value;
  fire(form, 'submit'); await tick();
  assert.equal(calls.filter((x) => x.options.method === 'POST').length, 0);
  assert.match(root.textContent, /100\.00/); assert.match(root.innerHTML, /Lender &lt;A&gt;/);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick();
  assert.match(root.textContent, /outcome is uncertain/i);
  fail = false; fire(root.querySelector('[data-retry]'), 'click'); await tick(); await tick();
  const writes = calls.filter((x) => x.options.method === 'POST');
  assert.equal(writes.length, 2); assert.deepEqual(writes[0].options.body, writes[1].options.body);
  assert.equal(writes[0].options.body.expected_amount, '100.00'); assert.equal(writes[0].options.body.kind, 'borrowing_external');
  assert.equal(writes[0].options.body.reviewed, true); dispose(); assert.equal(root.textContent, '');
});

function receiptApi() {
  const calls = []; const mapping = { id: uuid(6), book_id: book.book_id, treasury_account_id: uuid(3), version: 1, cash_snapshot: { code: '1030', name: 'Cash - Bank / GCash' } };
  let preparation;
  return { calls, async request(path, options = {}) {
    calls.push({ path, options });
    if (path.endsWith('/book')) return { book };
    if (path.endsWith('/workspace')) return { contract_version: 1, actor: { user_id: session.user.id, device_id: 'device' }, accounts: [{ id: uuid(3), alias: 'Private wallet', kind: 'gcash', balance: {}, actions: [] }], claims: [], capabilities: {}, blockers: [], enabled: true, owner_configured: true };
    if (path.endsWith('/cash-mapping')) return { book_id: book.book_id, treasury_account_id: uuid(3), mapping };
    if (path.includes('/accounts/') && path.includes('/receipts?')) return { items: [{ id: uuid(4), account_id: uuid(3), reference: 'Private <receipt>', amount: source().amount }], total_count: 1, limit: 50, offset: 0, has_more: false, totals: {} };
    if (path.includes('/review?')) return source();
    if (path.endsWith('/prepare')) { const { source_digest, ...snapshot } = source(); preparation = { id: uuid(20), request_id: options.body.request_id, book_id: book.book_id, treasury_account_id: uuid(3), receipt_id: uuid(4), event_id: uuid(5), mapping_id: uuid(6), source_digest, snapshot, actor_user_id: session.user.id, confirmation_token: 'b'.repeat(64) }; return { preparation, posting: null }; }
    if (path.endsWith('/post')) return { preparation, journal_entry_id: uuid(21), posting: { preparation_id: preparation.id, journal_entry_id: uuid(21), book_id: book.book_id, treasury_account_id: uuid(3), receipt_id: uuid(4), event_id: uuid(5), source_digest: digest, exact_posted: true, correction_pending: false } };
    throw Error(`Unexpected request ${path}`);
  } };
}
async function selectWallet(root) { const wallet = root.querySelector('[name="wallet"]'); wallet.value = uuid(3); fire(wallet, 'change'); await tick(); await tick(); }

test('receipt recognition needs separate review, preparation, and posting confirmation', async () => {
  const root = new Element(), api = receiptApi();
  await mountManagementSourceAccounting({ root, api, session, mode: 'receipts' });
  await selectWallet(root);
  fire(root.querySelector('[data-review-receipt]'), 'click'); await tick();
  assert.match(root.textContent, /Prepare receipt accounting/); assert.match(root.textContent, /90,071,992,547,409\.93/);
  assert.match(root.innerHTML, /Private &lt;receipt&gt;/);
  assert.equal(api.calls.filter((call) => call.options.method === 'POST').length, 0);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.match(root.textContent, /Receipt prepared for review/);
  assert.equal(api.calls.filter((call) => call.path.endsWith('/post')).length, 0);
  fire(root.querySelector('[data-post-receipt]'), 'click'); await tick();
  assert.match(root.textContent, /matching unapplied borrower liability/);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.match(root.textContent, /Receipt cash recognized/);
  const posts = api.calls.filter((call) => call.options.method === 'POST');
  assert.deepEqual(Object.keys(posts[0].options.body).sort(), ['mapping_id', 'request_id', 'source_digest']);
  assert.deepEqual(posts[1].options.body, { source_digest: digest, confirmation_token: 'b'.repeat(64), confirm: true });
});

test('cash mapping review binds evidence, wallet and current version', async () => {
  const root = new Element(), api = receiptApi();
  await mountManagementSourceAccounting({ root, api, session, mode: 'receipts' }); await selectWallet(root);
  const form = root.querySelector('[data-mapping-form]'); form.querySelector('[name="evidence_reference"]').value = 'Bank confirmation'; form.querySelector('[name="evidence_digest"]').value = digest;
  fire(form, 'submit'); await tick();
  assert.match(root.textContent, /Bank confirmation/); assert.match(root.textContent, /1030/);
  assert.equal(api.calls.filter((call) => call.options.method === 'POST').length, 0);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick();
  const write = api.calls.find((call) => call.options.method === 'POST');
  assert.equal(write.path, `${base}/treasury/accounts/${uuid(3)}/cash-mapping`);
  assert.equal(write.options.body.expected_version, 1); assert.equal(write.options.body.cash_code, '1030'); assert.equal(write.options.body.evidence_digest, digest);
  // This fixture returns an old mapping, so the client must retain the request.
  assert.match(root.textContent, /outcome is uncertain/i);
});

test('aborting a private receipt review prevents late source or controls appearing', async () => {
  const root = new Element(), controller = new AbortController(), api = receiptApi(); let finish;
  const original = api.request.bind(api); api.request = (path, options) => path.includes('/review?') ? new Promise((resolve) => { finish = resolve; }) : original(path, options);
  await mountManagementSourceAccounting({ root, api, session, signal: controller.signal, mode: 'receipts' }); await selectWallet(root);
  fire(root.querySelector('[data-review-receipt]'), 'click'); await tick(); controller.abort(); finish(source()); await tick();
  assert.equal(root.textContent, ''); assert.equal(api.calls.filter((call) => call.options.method === 'POST').length, 0);
});

test('permissions changing during receipt review erase loaded private wallet data', async () => {
  const root = new Element(), api = receiptApi(); let finish, current = structuredClone(session);
  const original = api.request.bind(api); api.request = (path, options) => path.includes('/review?') ? new Promise((resolve) => { finish = resolve; }) : original(path, options);
  await mountManagementSourceAccounting({ root, api, session: current, getSession: () => current, mode: 'receipts' }); await selectWallet(root);
  fire(root.querySelector('[data-review-receipt]'), 'click'); await tick();
  current = { ...current, permissions: ['accounting.view'] }; finish(source()); await tick(); await tick();
  assert.doesNotMatch(root.textContent, /Private wallet|Private <receipt>|90,071,992,547,409/);
  assert.equal(root.querySelector('[name="wallet"]'), null);
  assert.equal(root.querySelector('[data-confirm]'), null);
  assert.equal(api.calls.filter((call) => call.options.method === 'POST').length, 0);
});

test('a saved preparation from another wallet is rejected without posting controls', async () => {
  const root = new Element(), api = receiptApi(); const original = api.request.bind(api);
  api.request = (path, options) => path.includes('/receipt-preparations/') ? Promise.resolve({ preparation: { id: uuid(20), treasury_account_id: uuid(30), book_id: book.book_id }, posting: null }) : original(path, options);
  await mountManagementSourceAccounting({ root, api, session, mode: 'receipts' }); await selectWallet(root);
  const form = root.querySelector('[data-preparation-form]'); form.querySelector('[name="preparation_id"]').value = uuid(20); fire(form, 'submit'); await tick();
  assert.match(root.textContent, /incomplete/); assert.equal(root.querySelector('[data-post-receipt]'), null);
});

test('book setup offers only real book kinds and requires its own permanent confirmation', async () => {
  const root = new Element(), writes = []; let configuredBook = { status: 'unconfigured', book_id: null, kind: null, entity_label: null };
  await mountManagementSourceAccounting({ root, session, mode: 'book', api: { async request(path, options = {}) { if (options.method === 'POST') { writes.push(structuredClone(options.body)); configuredBook = { ...options.body, status: 'configured', book_id: book.book_id }; } return { book: configuredBook, can_configure: true }; } } });
  assert.doesNotMatch(root.innerHTML, /value="synthetic"/);
  const form = root.querySelector('[data-book-form]');
  for (const [name, value] of Object.entries({ kind: 'corporate_legal', entity_label: 'Actual Company', evidence_reference: 'Registration record', evidence_digest: digest })) form.querySelector(`[name="${name}"]`).value = value;
  fire(form, 'submit'); await tick(); assert.equal(writes.length, 0); assert.match(root.textContent, /cannot be changed/i);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(writes.length, 1); assert.equal(writes[0].confirm, true); assert.equal(writes[0].kind, 'corporate_legal'); assert.match(root.textContent, /Actual Company/); assert.equal(root.querySelector('[data-book-form]'), null);
});

test('liability settlement binds an existing obligation and exact posted debit', async () => {
  const data = schedule(); data.obligations = [{ obligation_id: uuid(13), book_id: book.book_id, kind: 'borrowing_external', counterparty: 'Lender A', due_date: null, account_code: '2300', recognized_amount: '100.00', outstanding_amount: '100.00' }];
  data.unregistered_lines = [{ journal_line_id: uuid(15), journal_entry_id: uuid(16), entry_number: 'GJ-2', account_code: '2300', posting_date: '2026-09-30', debit: '40.00', credit: '0.00', source_type: 'manual', source_reference: null, reversal_of_entry_id: null }];
  const writes = [], root = new Element();
  await mountManagementSourceAccounting({ root, session, mode: 'liabilities', api: { async request(path, options = {}) { if (path.endsWith('/book')) return { book }; if (options.method === 'POST') { writes.push({ path, body: options.body }); return { claim_id: uuid(17) }; } return data; } } });
  fire(root.querySelector('[data-movement-line]'), 'click');
  const form = root.querySelector('[data-liability-form]');
  for (const [name, value] of Object.entries({ obligation_id: uuid(13), evidence_reference: 'Settlement record', evidence_digest: digest })) form.querySelector(`[name="${name}"]`).value = value;
  fire(form, 'submit'); await tick(); assert.equal(writes.length, 0);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(writes[0].path, `${base}/liabilities/${uuid(13)}/movements`); assert.equal(writes[0].body.expected_amount, '40.00'); assert.equal(writes[0].body.kind, 'settlement'); assert.equal(writes[0].body.reverses_claim_id, null);
});
