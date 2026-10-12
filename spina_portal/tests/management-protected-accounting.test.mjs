import assert from 'node:assert/strict';
import test from 'node:test';
import { mountProtectedAccounting, applicationSource, cutoffCandidate } from '../assets/management-protected-accounting.js';
import { Element, fire } from './helpers/dom.mjs';

const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`, digest = 'a'.repeat(64);
const tick = () => new Promise((resolve) => setImmediate(resolve));
const book = { status: 'configured', book_id: id(1), kind: 'owner_operations', entity_label: 'Actual owner' };
const session = { user: { id: id(2), role: 'Management', roles: ['management'] }, permissions: ['accounting.view', 'accounting.journal.manage', 'accounting.period.close.prepare', 'accounting.period.close.post'] };
const app = (regular = false) => ({ book_id: id(1), treasury_account_id: id(3), application_id: id(4), receipt_id: id(5), transaction_id: id(6), event_id: id(7), loan_id: id(8), fiscal_period_id: id(9), posting_date: '2026-09-30', source_digest: digest, amount: '100.00', product_model: regular ? 'fixed_daily' : 'seven_by_seven', accounting_policy_version: regular ? 'treasury_regular_original_first_cash_v1' : 'treasury_seven_by_seven_application_v1', lines: [{ line_number: 1, account_code: '2200', debit: '100.00', credit: '0.00', account_snapshot: { name: 'Unapplied Borrower Funds' } }, { line_number: 2, account_code: regular ? '1100' : '1110', debit: '0.00', credit: '90.00', account_snapshot: { name: 'Loans Receivable' } }, { line_number: 3, account_code: regular ? '4000' : '4010', debit: '0.00', credit: '10.00', account_snapshot: { name: 'Interest Income' } }, { line_number: 4, account_code: '1120', debit: '10.00', credit: '0.00', account_snapshot: { name: 'Accrued interest' } }, { line_number: 5, account_code: '1120', debit: '0.00', credit: '10.00', account_snapshot: { name: 'Accrued interest' } }], origin: { secret: 'DO NOT DISPLAY' } });
const candidate = (ready = true) => ({ book, period_id: id(9), loan_id: id(8), ready, blockers: ready ? [] : ['elapsed_eir_boundary_adapter_required'], source_digest: ready ? digest : null, current_confirmation: false, preparation_id: null, confirmation_id: null, cutoff_date: ready ? '2026-09-30' : null, policy_version: ready ? 'regular_release_day_cutoff_assessment_v1' : null, measurement: ready ? { id: id(10), date: '2026-09-30', version: 1, calculation_digest: digest, ecl_amount: '4.00' } : null, balances: ready ? { '1100': '100.00', '1110': '0.00', '1120': '0.00', '1190': '4.00' } : null, boundary: ready ? { anchor_date: '2026-09-30', release_source_key: 'loan-release:actual' } : null, comprehensive_source_coverage: false });
function fixture({ ready = true, blocked = false, regular = false } = {}) {
  const writes = []; let prep;
  return { writes, async request(path, options = {}) {
    if (path.endsWith('/book')) return { book };
    if (path.endsWith('/workspace')) return { contract_version: 1, actor: { user_id: id(2), device_id: 'device' }, enabled: true, owner_configured: true, accounts: [{ id: id(3), alias: 'Authorized wallet', kind: 'gcash', balance: {}, actions: [] }], claims: [], capabilities: {}, blockers: [] };
    if (options.method === 'POST') { writes.push({ path, body: structuredClone(options.body) }); if (path.includes('/applications/')) { const { source_digest, ...snapshot } = app(regular); prep = { id: id(20), request_id: options.body.request_id, ...Object.fromEntries(['book_id', 'application_id', 'transaction_id', 'receipt_id', 'treasury_account_id', 'loan_id'].map((key) => [key, snapshot[key]])), source_digest, snapshot, actor_user_id: id(2), confirmation_token: 'b'.repeat(64) }; return { preparation: prep, posting: null }; } if (path.endsWith('/post')) return { preparation: prep, journal_entry_id: id(21), posting: { ...prep, preparation_id: prep.id, journal_entry_id: id(21), event_id: id(7), exact_posted: true, correction_pending: false } }; return path.endsWith('/prepare') ? { preparation_id: id(20) } : { confirmation_id: id(21) }; }
    if (path.endsWith('/review')) { if (blocked) throw Error('Regular loan application accounting is not supported.'); return app(regular); }
    if (path.includes('/period-assessments/')) return candidate(ready);
    return { fiscal_periods: [{ period_id: id(9), label: 'September' }] };
  } };
}
async function lookup(root, mode) { const form = root.querySelector('[data-source-lookup]'); form.querySelector(`[name="${mode === 'applications' ? 'application_id' : 'loan_id'}"]`).value = mode === 'applications' ? id(4) : id(8); const choice = form.querySelector('select'); choice.value = mode === 'applications' ? id(3) : id(9); fire(form, 'submit'); await tick(); await tick(); }

test('application review retains exact EIR coordinates without rendering private origin snapshots', async () => {
  const root = new Element(), api = fixture(); await mountProtectedAccounting({ root, api, session, mode: 'applications' }); await lookup(root, 'applications');
  assert.match(root.textContent, /Interest Income/); assert.doesNotMatch(root.textContent, /DO NOT DISPLAY/); assert.equal(api.writes.length, 0);
  fire(root.querySelector('[data-prepare-application]'), 'click'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(api.writes.length, 1); assert.equal(api.writes[0].body.source_digest, digest); assert.ok(api.writes[0].body.request_id);
  fire(root.querySelector('[data-post-application]'), 'click'); await tick(); assert.equal(api.writes.length, 1); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(api.writes.length, 2); assert.match(root.textContent, /Application accounting posted/); assert.match(root.textContent, /No cash is recognized again/);
});
test('unsupported applications show the server reason without preparation controls', async () => { const root = new Element(), api = fixture({ blocked: true }); await mountProtectedAccounting({ root, api, session, mode: 'applications' }); await lookup(root, 'applications'); assert.match(root.textContent, /Regular loan application accounting is not supported/); assert.equal(root.querySelector('[data-prepare-application]'), null); assert.equal(api.writes.length, 0); });
test('cutoff proof requires rationale, preparation and a separate exact confirmation', async () => { const root = new Element(), api = fixture(); await mountProtectedAccounting({ root, api, session, mode: 'assessments' }); await lookup(root, 'assessments'); const form = root.querySelector('[data-assessment-prepare]'); form.querySelector('[name="review_rationale"]').value = 'Reviewed actual dated allowance and protected release evidence.'; fire(form, 'submit'); await tick(); assert.equal(api.writes.length, 0); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick(); assert.equal(api.writes.length, 1); fire(root.querySelector('[data-confirm-assessment]'), 'click'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick(); assert.equal(api.writes.length, 2); assert.deepEqual(api.writes[1].body, { expected_book_id: id(1), source_digest: digest, confirm: true }); });
test('unsupported cutoff states expose no monetary proof and cannot be acknowledged away', async () => { const root = new Element(), api = fixture({ ready: false }); await mountProtectedAccounting({ root, api, session, mode: 'assessments' }); await lookup(root, 'assessments'); assert.match(root.textContent, /elapsed|Elapsed/); assert.equal(root.querySelector('[data-assessment-prepare]'), null); assert.equal(root.querySelector('[data-confirm-assessment]'), null); assert.equal(api.writes.length, 0); });
test('scope mismatches and invented cutoff money are rejected', () => { assert.throws(() => applicationSource(app(), { bookId: id(1), accountId: id(30), applicationId: id(4) })); assert.throws(() => cutoffCandidate({ ...candidate(false), balances: { '1100': '0.00' } }, { bookId: id(1), periodId: id(9), loanId: id(8) })); });
test('cutoff display projection drops unexpected nested private source details', () => {
  const value = candidate(); value.balances.private_snapshot = 'PRIVATE'; value.measurement.private_snapshot = { private: 'PRIVATE' }; value.boundary.private_snapshot = 'PRIVATE'; value.snapshot = { private: 'PRIVATE' };
  const projected = cutoffCandidate(value, { bookId: id(1), periodId: id(9), loanId: id(8) });
  assert.doesNotMatch(JSON.stringify(projected), /PRIVATE|private_snapshot/);
});

test('cutoff preparation retry retains the identical rationale and source after an uncertain response', async () => {
  const root = new Element(), api = fixture(), attempts = []; let fail = true; const original = api.request.bind(api);
  api.request = async (path, options = {}) => { if (options.method === 'POST') { attempts.push(structuredClone(options.body)); if (fail) throw Error('Lost response'); } return original(path, options); };
  await mountProtectedAccounting({ root, api, session, mode: 'assessments' }); await lookup(root, 'assessments');
  const form = root.querySelector('[data-assessment-prepare]'); form.querySelector('[name="review_rationale"]').value = 'Reviewed actual dated allowance and protected release evidence.';
  fire(form, 'submit'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick();
  fail = false; fire(root.querySelector('[data-retry]'), 'click'); await tick(); await tick();
  assert.deepEqual(attempts[0], attempts[1]); assert.equal(attempts.length, 2); assert.ok(root.querySelector('[data-confirm-assessment]'));
});
test('view-only cutoff users cannot prepare despite a supported candidate', async () => { const root = new Element(), api = fixture(); await mountProtectedAccounting({ root, api, session: { ...session, permissions: ['accounting.view'] }, mode: 'assessments' }); await lookup(root, 'assessments'); assert.equal(root.querySelector('[data-assessment-prepare]'), null); assert.match(root.textContent, /preparation permission is required/); assert.equal(api.writes.length, 0); });
test('abort discards a delayed private application response and detached review actions', async () => {
  const root = new Element(), api = fixture(), controller = new AbortController(); let finish; const original = api.request.bind(api);
  api.request = (path, options = {}) => path.endsWith('/review') ? new Promise((resolve) => { finish = resolve; }) : original(path, options);
  await mountProtectedAccounting({ root, api, session, signal: controller.signal, mode: 'applications' });
  const form = root.querySelector('[data-source-lookup]'); form.querySelector('[name="application_id"]').value = id(4); form.querySelector('select').value = id(3); fire(form, 'submit'); await tick();
  controller.abort(); finish(app()); await tick(); assert.equal(root.textContent, ''); assert.equal(api.writes.length, 0);
});

test('permissions changing during application review erase loaded private wallet data', async () => {
  const root = new Element(), api = fixture(); let finish, current = structuredClone(session); const original = api.request.bind(api);
  api.request = (path, options = {}) => path.endsWith('/review') ? new Promise((resolve) => { finish = resolve; }) : original(path, options);
  await mountProtectedAccounting({ root, api, session: current, getSession: () => current, mode: 'applications' });
  const form = root.querySelector('[data-source-lookup]'); form.querySelector('[name="application_id"]').value = id(4); form.querySelector('select').value = id(3); fire(form, 'submit'); await tick();
  current = { ...current, permissions: ['accounting.view'] }; finish(app()); await tick(); await tick();
  assert.doesNotMatch(root.textContent, /Authorized wallet|Interest Income/);
  assert.equal(root.querySelector('[data-source-lookup]'), null);
  assert.equal(root.querySelector('[data-prepare-application]'), null);
  assert.equal(api.writes.length, 0);
});

test('Regular review retains its original-contract basis and retries the same preparation request', async () => {
  const root = new Element(), api = fixture({ regular: true }), original = api.request.bind(api); let lost = false;
  api.request = async (path, options = {}) => {
    const result = await original(path, options);
    if (!lost && options.method === 'POST' && path.includes('/applications/')) { lost = true; throw Error('Response lost'); }
    return result;
  };
  await mountProtectedAccounting({ root, api, session, mode: 'applications' }); await lookup(root, 'applications');
  assert.match(root.textContent, /Original contract, first cash payment/);
  assert.doesNotMatch(root.textContent, /DO NOT DISPLAY/);
  fire(root.querySelector('[data-prepare-application]'), 'click'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  fire(root.querySelector('[data-retry]'), 'click'); await tick(); await tick();
  assert.equal(api.writes.length, 2); assert.deepEqual(api.writes[0], api.writes[1]);
  fire(root.querySelector('[data-post-application]'), 'click'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(api.writes.length, 3); assert.match(root.textContent, /Application accounting posted/);
});

test('a preparation cannot substitute another valid product policy behind the reviewed digest', async () => {
  const root = new Element(), api = fixture(), original = api.request.bind(api);
  api.request = async (path, options = {}) => {
    const result = await original(path, options);
    if (options.method === 'POST' && path.includes('/applications/')) {
      const { source_digest, ...snapshot } = app(true); result.preparation.snapshot = snapshot;
    }
    return result;
  };
  await mountProtectedAccounting({ root, api, session, mode: 'applications' }); await lookup(root, 'applications');
  fire(root.querySelector('[data-prepare-application]'), 'click'); await tick(); fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(root.querySelector('[data-post-application]'), null); assert.equal(api.writes.length, 1);
});

for (const closed of [false, true]) test(`${closed ? 'closed term' : 'full payoff'} requires source evidence and a separately confirmed retained treatment`, async () => {
  const root = new Element(), api = fixture({ regular: true }), original = api.request.bind(api), writes = [];
  const value = { ready: true, blockers: [], book_id: id(1), treasury_account_id: id(3), application_id: id(4), source_digest: digest,
    contract_evidence_reference: 'SIGNED-ORIGINAL', review_id: null,
    ...(closed ? { loan_id: id(8), contractual_due_date: '2026-09-20', treatment: 'original_eir_through_maturity_no_extension' }
      : { amount: '1200.00', gross_carrying_before: '1150.00', settlement_difference: '50.00' }), origin: { secret: 'DO NOT DISPLAY' } };
  api.request = async (path, options = {}) => {
    if (path.endsWith(closed ? '/closed-term-review' : '/payoff-review')) {
      if (options.method === 'POST') { writes.push(structuredClone(options.body)); return { ...value, review_id: id(31) }; }
      return value;
    }
    return original(path, options);
  };
  await mountProtectedAccounting({ root, api, session, mode: 'applications' });
  const lookupForm = root.querySelector('[data-source-lookup]'); lookupForm.querySelector('[name="application_id"]').value = id(4); lookupForm.querySelector('select').value = id(3);
  fire(root.querySelector(closed ? '[data-load-closed-term]' : '[data-load-payoff]'), 'click'); await tick(); await tick();
  assert.doesNotMatch(root.textContent, /DO NOT DISPLAY/);
  const form = root.querySelector(closed ? '[data-closed-term-review]' : '[data-payoff-review]'); assert.ok(form);
  form.querySelector('[name="contract_reference"]').value = 'WRONG'; form.querySelector('[name="rationale"]').value = 'I reviewed the actual signed contractual treatment and retained source.';
  form.querySelector(closed ? '[name="term_confirm"]' : '[name="no_rebate"]').checked = true;
  fire(form, 'submit'); await tick(); assert.equal(writes.length, 0); assert.equal(root.querySelector('[data-confirm]'), null);
  form.querySelector('[name="contract_reference"]').value = 'SIGNED-ORIGINAL'; fire(form, 'submit'); await tick(); assert.equal(writes.length, 0);
  fire(root.querySelector('[data-confirm]'), 'click'); await tick(); await tick();
  assert.equal(writes.length, 1); assert.equal(writes[0].source_digest, digest); assert.equal(writes[0].confirm, true);
  assert.equal(writes[0].treatment, closed ? 'original_eir_through_maturity_no_extension' : 'full_contractual_payoff_no_rebate');
  assert.ok(root.querySelector('[data-payoff-reviewed]')); assert.equal(root.querySelector('[data-post-application]'), null);
});
