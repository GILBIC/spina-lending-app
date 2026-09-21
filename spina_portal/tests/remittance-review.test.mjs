import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { ApiError } from '../assets/api.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/remittance-review.js', import.meta.url);
const RECIPIENT = '11111111-1111-4111-8111-111111111111';
const COLLECTOR = '22222222-2222-4222-8222-222222222222';
const REMITTANCE = '33333333-3333-4333-8333-333333333333';
const NOTICE = '44444444-4444-4444-8444-444444444444';
const TRANSACTION = '55555555-5555-4555-8555-555555555555';
const CLIENT = '66666666-6666-4666-8666-666666666666';
const LOAN = '77777777-7777-4777-8777-777777777777';
const RELEASE = '88888888-8888-4888-8888-888888888888';
const SESSION = { user: { id: RECIPIENT, roles: ['employee'] }, permissions: ['remittance.view', 'remittance.receive'] };
const notice = { notification_id: NOTICE, remittance_id: REMITTANCE,
  recipient_user_id: RECIPIENT, sender_user_id: COLLECTOR, remittance_number: 'REM-REVIEW-001',
  collector_name: 'Test Collector', total_amount: '90.00', transaction_count: 1,
  client_count: 1, collection_date: '2026-09-21', status: 'pending', is_pending: true };

function record() {
  return { remittance_id: REMITTANCE, remittance_number: 'REM-REVIEW-001',
    recipient_user_id: RECIPIENT, recipient_name: 'Test Employee', collector_user_id: COLLECTOR,
    collector_name: 'Test Collector', collection_date: '2026-09-21', status: 'submitted',
    transaction_count: 1, payment_count: 1, unable_to_pay_count: 0, covered_payment_count: 1,
    client_count: 1, total_amount: '90.00', note: 'Office cash handover',
    submitted_at: '2026-09-21T04:00:00Z', received_at: null,
    items: [{ transaction_id: TRANSACTION, client_id: CLIENT, client_name: 'Test <Borrower>',
      loan_id: LOAN, loan_type: 'Regular', collection_date: '2026-09-21', entry_type: 'advance',
      amount: '100.00', receipt_number: 'RCPT-TEST-001', accepted_at: '2026-09-21T03:00:00Z',
      note: 'Two covered dates', covered_dates: ['2026-09-21', '2026-09-22'] }],
    refund_due_release_count: 1, refund_due_release_total: '10.00',
    refund_due_releases: [{ release_id: RELEASE, approval_id: NOTICE, adjustment_id: TRANSACTION,
      client_id: CLIENT, client_name: 'Test <Borrower>', loan_id: LOAN, loan_type: 'Regular',
      released_at: '2026-09-21T03:30:00Z', amount: '10.00', evidence_reference: 'REFUND-EVIDENCE-001',
      evidence_digest: 'a'.repeat(64), cash_effect: 'outflow' }] };
}

function accepted() {
  return { notification: { ...notice, is_pending: false, status: 'accepted' },
    remittance_id: REMITTANCE, remittance_number: 'REM-REVIEW-001', status: 'received',
    received_at: '2026-09-21T04:05:00Z', custody_user_id: RECIPIENT,
    custody_message: 'Money is now under your custody.' };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function harness({ session = SESSION, notifications = [notice] } = {}) {
  assert.equal(existsSync(moduleUrl), true, 'Recipient full remittance review must exist');
  const { mountRemittanceReview } = await import(moduleUrl.href);
  const h = { root: new Element(), controller: new AbortController(), calls: [], online: true,
    records: [record()], response: accepted(), session, notifications };
  h.api = { async request(path, options = {}) {
    h.calls.push({ path, options });
    if (options.method === 'POST') {
      if (h.writeError) throw h.writeError;
      return h.writePending?.promise ?? h.response;
    }
    if (h.readError) throw h.readError;
    return h.readPending?.promise ?? h.records;
  } };
  h.dispose = mountRemittanceReview({ root: h.root, api: h.api, session, notifications,
    signal: h.controller.signal, isOnline: () => h.online });
  return h;
}

function reviewButton(h) { return h.root.querySelector('[data-review-notification]'); }
function postCalls(h) { return h.calls.filter((call) => call.options.method === 'POST'); }
async function open(h) {
  assert.ok(reviewButton(h), 'A pending recipient must have a Review remittance action');
  fire(reviewButton(h), 'click');
  await setImmediate();
}
function check(h, name) {
  const input = h.root.querySelector(`[name="${name}"]`);
  assert.ok(input, `Missing ${name} checkbox`);
  input.checked = true;
  fire(input, 'change');
}
function accept(h) { fire(h.root.querySelector('[data-remittance-accept-form]'), 'submit'); }

test('pending summary offers review and never acceptance or a financial request', async (t) => {
  const h = await harness(); t.after(h.dispose);
  assert.match(reviewButton(h).textContent, /Review remittance/);
  assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
  assert.equal(h.calls.length, 0);
  await open(h);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].path, '/api/v1/remittances');
  assert.equal(h.calls[0].options.method ?? 'GET', 'GET');
  assert.equal(postCalls(h).length, 0);
});

test('review renders every receipt, covered date and refund cash outflow from authoritative detail', async (t) => {
  const h = await harness(); t.after(h.dispose);
  await open(h);
  const detail = h.root.querySelector('[data-remittance-detail]');
  assert.equal(detail.querySelectorAll('[data-remittance-item]').length, 1);
  assert.match(detail.innerHTML, /Test &lt;Borrower&gt;/);
  for (const value of ['RCPT-TEST-001', 'Regular', '2026-09-21', '2026-09-22', '100.00', '90.00', 'REFUND-EVIDENCE-001', '10.00']) {
    assert.ok(detail.textContent.includes(value), `Missing review evidence ${value}`);
  }
  assert.equal(detail.querySelectorAll('[data-remittance-refund]').length, 1);
  assert.match(detail.textContent, /cash outflow/i);
  assert.equal(detail.querySelector('[name="reviewedPayments"]').checked || false, false);
  assert.equal(detail.querySelector('[name="physicallyReceived"]').checked || false, false);
});

test('both explicit acknowledgements are needed even when the submit event is dispatched directly', async (t) => {
  const h = await harness(); t.after(h.dispose);
  await open(h);
  const submit = h.root.querySelector('button[data-remittance-accept]');
  assert.equal(submit.disabled, true);
  accept(h);
  check(h, 'reviewedPayments');
  accept(h);
  await setImmediate();
  assert.equal(postCalls(h).length, 0);
  assert.equal(submit.disabled, true);
  check(h, 'physicallyReceived');
  assert.equal(submit.disabled, false);
  accept(h);
  await setImmediate();
  assert.equal(postCalls(h).length, 1);
  assert.equal(postCalls(h)[0].path, `/api/v1/notifications/${NOTICE}/accept-remittance`);
  assert.deepEqual(postCalls(h)[0].options.body, { review_acknowledged: true });
  assert.equal(postCalls(h)[0].options.financial, true);
  assert.match(h.root.textContent, /cash custody.*recorded|money.*custody/i);
  assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
  assert.equal(reviewButton(h), null);
});

test('physical acknowledgement alone cannot transfer custody', async (t) => {
  const h = await harness(); t.after(h.dispose);
  await open(h); check(h, 'physicallyReceived'); accept(h);
  await setImmediate();
  assert.equal(postCalls(h).length, 0);
});

test('closing review clears acknowledgements and stale submit cannot accept', async (t) => {
  const h = await harness(); t.after(h.dispose);
  await open(h); check(h, 'reviewedPayments'); check(h, 'physicallyReceived');
  const form = h.root.querySelector('[data-remittance-accept-form]');
  const reviewed = h.root.querySelector('[name="reviewedPayments"]');
  fire(h.root.querySelector('[data-remittance-close]'), 'click');
  assert.equal(reviewed.checked, false);
  assert.equal(h.root.querySelector('[data-remittance-detail]').innerHTML, '');
  fire(form, 'submit');
  assert.equal(postCalls(h).length, 0);
  await open(h);
  assert.equal(h.calls.length, 2, 'Reopening must refresh authoritative detail');
  assert.equal(h.root.querySelector('[name="reviewedPayments"]').checked || false, false);
});

for (const fixture of [
  { label: 'no view', session: { ...SESSION, permissions: ['remittance.receive'] } },
  { label: 'no receive', session: { ...SESSION, permissions: ['remittance.view'] } },
  { label: 'different recipient', notifications: [{ ...notice, recipient_user_id: COLLECTOR }] },
  { label: 'sender is self', notifications: [{ ...notice, sender_user_id: RECIPIENT }] },
  { label: 'already accepted', notifications: [{ ...notice, is_pending: false, status: 'accepted' }] },
]) {
  test(`no financial review action for ${fixture.label}`, async (t) => {
    const h = await harness(fixture); t.after(h.dispose);
    assert.equal(reviewButton(h), null);
    assert.equal(h.calls.length, 0);
  });
}

for (const mutation of [
  ['missing selected record', (h) => { h.records = []; }],
  ['duplicate selected record', (h) => { h.records.push(record()); }],
  ['recipient mismatch', (h) => { h.records[0].recipient_user_id = COLLECTOR; }],
  ['collector mismatch', (h) => { h.records[0].collector_user_id = RECIPIENT; }],
  ['already received', (h) => { h.records[0].status = 'received'; }],
  ['missing payment', (h) => { h.records[0].items = []; }],
  ['invalid payment amount', (h) => { h.records[0].items[0].amount = 'not money'; }],
  ['missing covered dates', (h) => { delete h.records[0].items[0].covered_dates; }],
  ['missing refund release', (h) => { h.records[0].refund_due_releases = []; }],
]) {
  test(`${mutation[0]} prevents rendering an acceptance form`, async (t) => {
    const h = await harness(); t.after(h.dispose); mutation[1](h);
    await open(h);
    assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
    assert.equal(postCalls(h).length, 0);
    assert.match(h.root.textContent, /could not|unavailable|refresh/i);
  });
}

test('read failure leaves custody pending and does not expose an acceptance form', async (t) => {
  const h = await harness(); t.after(h.dispose);
  h.readError = new ApiError('private server error', { status: 503 });
  await open(h);
  assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
  assert.equal(postCalls(h).length, 0);
  assert.doesNotMatch(h.root.textContent, /private server error/);
});

test('offline review makes no GET and offline acceptance makes no POST', async (t) => {
  const h = await harness(); t.after(h.dispose);
  h.online = false; await open(h);
  assert.equal(h.calls.length, 0);
  h.online = true; await open(h);
  check(h, 'reviewedPayments'); check(h, 'physicallyReceived');
  h.online = false; accept(h);
  assert.equal(postCalls(h).length, 0);
  assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
  assert.match(h.root.textContent, /online|connection|internet/i);
});

test('duplicate acceptance events produce one request while result is pending', async (t) => {
  const h = await harness(); t.after(h.dispose);
  await open(h); check(h, 'reviewedPayments'); check(h, 'physicallyReceived');
  h.writePending = deferred();
  const form = h.root.querySelector('[data-remittance-accept-form]');
  fire(form, 'submit'); fire(form, 'submit'); fire(reviewButton(h), 'click');
  assert.equal(postCalls(h).length, 1);
  assert.equal(h.calls.length, 2);
  h.writePending.resolve(accepted()); await setImmediate();
});

for (const failure of ['network', 'server', 'malformed', 'wrong-custodian', 'wrong-remittance']) {
  test(`unconfirmed acceptance ${failure} locks replay and never claims custody`, async (t) => {
    const h = await harness(); t.after(h.dispose);
    await open(h); check(h, 'reviewedPayments'); check(h, 'physicallyReceived');
    if (failure === 'network') h.writeError = new ApiError('private failure', { code: 'network_uncertain' });
    if (failure === 'server') h.writeError = new ApiError('private failure', { status: 503 });
    if (failure === 'malformed') h.response = {};
    if (failure === 'wrong-custodian') h.response.custody_user_id = COLLECTOR;
    if (failure === 'wrong-remittance') h.response.remittance_id = CLIENT;
    const form = h.root.querySelector('[data-remittance-accept-form]');
    const review = reviewButton(h);
    fire(form, 'submit'); await setImmediate();
    fire(form, 'submit'); fire(review, 'click'); await setImmediate();
    assert.equal(h.calls.length, 2);
    assert.match(h.root.textContent, /not confirm|unconfirmed/i);
    assert.match(h.root.textContent, /Refresh/);
    assert.doesNotMatch(h.root.textContent, /Money is now|custody is now recorded|private failure/);
    assert.equal(h.root.querySelector('[data-remittance-accept-form]'), null);
  });
}

for (const phase of ['read', 'accept']) {
  test(`abort clears private detail and ignores late ${phase} response`, async (t) => {
    const h = await harness(); t.after(h.dispose);
    const pending = deferred();
    if (phase === 'read') { h.readPending = pending; await open(h); }
    else {
      await open(h); check(h, 'reviewedPayments'); check(h, 'physicallyReceived');
      h.writePending = pending; accept(h);
    }
    h.controller.abort();
    assert.equal(h.root.innerHTML, '');
    pending.resolve(phase === 'read' ? [record()] : accepted()); await setImmediate();
    assert.equal(h.root.innerHTML, '');
    assert.equal(h.calls.at(-1).options.signal.aborted, true);
  });
}

test('Employee workspace wires review and disposes it before remount', async (t) => {
  const root = new Element();
  const controller = new AbortController(); t.after(() => controller.abort());
  const calls = [];
  const context = { root, session: SESSION, signal: controller.signal, setNavigation() {},
    api: { async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/notifications') return [notice];
      if (path === '/api/v1/remittances') return [record()];
      return {};
    } } };
  await mountEmployeeWorkspace(context);
  const reviewRoot = root.querySelector('[data-remittance-review]');
  assert.ok(reviewRoot, 'Employee remittance section must mount the full review');
  fire(reviewRoot.querySelector('[data-review-notification]'), 'click'); await setImmediate();
  const form = reviewRoot.querySelector('[data-remittance-accept-form]');
  assert.ok(form);
  await mountEmployeeWorkspace(context);
  assert.equal(reviewRoot.innerHTML, '');
  fire(form, 'submit');
  assert.equal(calls.filter((call) => call.options.method === 'POST').length, 0);
});
