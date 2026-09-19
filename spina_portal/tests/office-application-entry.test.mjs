import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { SpinaApi } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/office-application-entry.js', import.meta.url);
const CLIENT = '11111111-1111-4111-8111-111111111111';
const APPLICATION = '22222222-2222-4222-8222-222222222222';
const VERSION = '33333333-3333-4333-8333-333333333333';
const CIF = '44444444-4444-4444-8444-444444444444';
const PRODUCT = '55555555-5555-4555-8555-555555555555';
const NEXT_VERSION = '66666666-6666-4666-8666-666666666666';
const OTHER_CIF = '77777777-7777-4777-8777-777777777777';
const REFERENCE = 'Loan / MixedCase-017';
const PERMISSION = 'client_onboarding.requirement.review';
const BASE = `/api/v1/management/clients/${CLIENT}/loan-applications`;

async function loadMount() {
  assert.ok(existsSync(moduleUrl), 'Office application entry is not implemented');
  const { mountOfficeApplicationEntry } = await import(moduleUrl.href);
  assert.equal(typeof mountOfficeApplicationEntry, 'function');
  return mountOfficeApplicationEntry;
}

function information() {
  return {
    request: {
      requested_loan_type_id: PRODUCT, purpose: 'Synthetic inventory',
      requested_amount: '123456789012345678901234567890.12',
      requested_payment_arrangement: 'Weekly in office', requested_term: 'Six weeks',
      preferred_first_payment_date: '2026-10-02',
    },
    repayment: {
      repayment_source: 'Synthetic shop income', source_details: 'Synthetic sales receipts',
      monthly_gross_income: '1.234567890123456789E+40', monthly_net_income: '-12345678901234567890.01',
      has_existing_obligations: true,
      obligations: [{ creditor: 'Synthetic creditor', outstanding_balance: '0.00', periodic_payment_amount: '1500.25', payment_frequency: 'Monthly', notes: 'Synthetic debt note' }],
    },
  };
}

function review() {
  return {
    client_id: CLIENT, application_id: APPLICATION, application_version_id: VERSION,
    application_reference: REFERENCE, cif_version_id: CIF, cif_version_number: 4,
    version_number: 9, information: information(), missing_fields: [],
    recorded_at: '2026-09-19T02:03:04Z', review_scope: 'loan_application_information_only',
    requested_loan_type_name: 'Synthetic product',
  };
}

function context() {
  return { client_id: CLIENT, cif_version_id: CIF, cif_version_number: 4,
    loan_types: [{ id: PRODUCT, code: 'SYNTH', name: 'Synthetic product' }] };
}

function response(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function harness({ role = 'employee', permissions = [PERMISSION], append = false } = {}) {
  const h = { root: new Element(), calls: [], context: context(), review: append ? review() : null,
    clientId: CLIENT, applicationReference: ` ${REFERENCE} `, controller: new AbortController(), saved: [], cancelled: [], fetch: null };
  h.signal = h.controller.signal;
  h.session = { user: { role, roles: [role] }, permissions, access_token: 'synthetic-token' };
  h.onSaved = (saved) => h.saved.push(saved);
  h.onCancel = (result) => h.cancelled.push(result);
  h.api = new SpinaApi({
    sessionStore: { load: () => h.session, deviceId: () => 'synthetic-office-device', clear() {} },
    fetchImpl(path, init) {
      h.calls.push({ path, init });
      if (h.fetch) return h.fetch(path, init);
      if (init.method === 'GET') return Promise.resolve(response(h.context));
      const body = JSON.parse(init.body);
      const { cif_version_number, requested_loan_type_name, ...saved } = review();
      return Promise.resolve(response({ ...saved, cif_version_id: body.cif_version_id,
        information: body.information, application_version_id: NEXT_VERSION,
        version_number: h.review ? h.review.version_number + 1 : 1 }, h.review ? 200 : 201));
    },
  });
  return h;
}

function field(h, name) { return h.root.querySelector(`[name="${name}"]`); }
function button(h, label) { return h.root.querySelectorAll('button').find((item) => item.textContent === label); }
function enter(h, name, value) { field(h, name).value = value; fire(field(h, name), 'change'); }
function submit(h) { assert.equal(fire(h.root.querySelector('form'), 'submit').defaultPrevented, true); }
function body(h) { return JSON.parse(h.calls.at(-1).init.body); }
function fill(h, facts = information()) {
  for (const [name, value] of Object.entries(facts.request)) enter(h, name, value ?? '');
  for (const [name, value] of Object.entries(facts.repayment)) {
    if (name !== 'obligations') enter(h, name, value === null ? '' : String(value));
  }
  facts.repayment.obligations.forEach((row, index) => {
    fire(button(h, 'Add obligation'), 'click');
    for (const [name, value] of Object.entries(row)) enter(h, `obligation_${index}_${name}`, value ?? '');
  });
}

for (const role of ['employee', ' Management ']) {
  test(`${role}: create authenticates context and one exact draft POST with every entered fact`, async () => {
    const mount = await loadMount();
    const h = harness({ role });
    const dispose = mount(h);
    assert.equal(typeof dispose, 'function');
    assert.deepEqual(h.calls.map(({ path }) => path), [`${BASE}/entry-context`]);
    await setImmediate();
    assert.match(h.root.textContent, /Source CIF version 4/);
    assert.match(h.root.textContent, /Requested information only; approval and release are separate/);
    assert.match(h.root.textContent, /incomplete draft/i);
    assert.equal(field(h, 'requested_amount').getAttribute('type'), 'text');
    assert.equal(field(h, 'has_existing_obligations').value, '');
    assert.equal(field(h, 'requested_loan_type_id').value, '');
    fill(h);
    const oldAmount = field(h, 'requested_amount');
    submit(h);
    await setImmediate();
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].path, `${BASE}/drafts`);
    assert.equal(h.calls[1].init.method, 'POST');
    assert.deepEqual(body(h), { cif_version_id: CIF, application_reference: REFERENCE, information: information() });
    for (const { init } of h.calls) {
      assert.equal(init.headers.Authorization, 'Bearer synthetic-token');
      assert.equal(init.headers['X-Device-Id'], 'synthetic-office-device');
    }
    assert.equal(h.saved.length, 1);
    assert.equal(oldAmount.value, '');
    assert.equal(h.root.querySelector('form'), null);
    dispose();
    assert.equal(h.root.innerHTML, '');
  });
}

test('blank draft stays nullable, explicit no obligations stays false, and zero remains exact text', async () => {
  const mount = await loadMount();
  const h = harness();
  mount(h);
  await setImmediate();
  enter(h, 'purpose', '   ');
  enter(h, 'monthly_gross_income', '0.00');
  enter(h, 'has_existing_obligations', 'false');
  submit(h);
  await setImmediate();
  assert.deepEqual(body(h).information, {
    request: { requested_loan_type_id: null, purpose: null, requested_amount: null, requested_payment_arrangement: null, requested_term: null, preferred_first_payment_date: null },
    repayment: { repayment_source: null, source_details: null, monthly_gross_income: '0.00', monthly_net_income: null, has_existing_obligations: false, obligations: [] },
  });
});

test('append prefills every fact and preserves the original while sending exact expected version', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  const original = structuredClone(h.review);
  mount(h);
  await setImmediate();
  for (const [name, value] of Object.entries(original.information.request)) assert.equal(field(h, name).value, value ?? '');
  assert.equal(field(h, 'monthly_net_income').value, '-12345678901234567890.01');
  assert.equal(field(h, 'obligation_0_notes').value, 'Synthetic debt note');
  enter(h, 'purpose', 'Changed purpose');
  submit(h);
  await setImmediate();
  assert.equal(h.calls[1].path, `${BASE}/${APPLICATION}/draft-versions`);
  assert.deepEqual(body(h), { cif_version_id: CIF, expected_version_number: 9,
    information: { ...original.information, request: { ...original.information.request, purpose: 'Changed purpose' } } });
  assert.deepEqual(h.review, original);
  assert.equal(h.saved.length, 1);
});

test('an identical append may return the same saved version without claiming another version', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  h.fetch = (_, init) => Promise.resolve(response(init.method === 'GET' ? h.context : h.review));
  mount(h);
  await setImmediate();
  submit(h);
  await setImmediate();
  assert.equal(h.saved.length, 1);
  assert.equal(h.saved[0].version_number, 9);
});

test('normal saves accept server-normalized text and decimal spelling without altering submitted money', async () => {
  const mount = await loadMount();
  const h = harness();
  const saved = { ...review(), version_number: 1, application_version_id: NEXT_VERSION };
  saved.information.request.purpose = 'Synthetic inventory';
  saved.information.request.requested_amount = '1E+3';
  h.fetch = (_, init) => Promise.resolve(response(init.method === 'GET' ? h.context : saved));
  mount(h);
  await setImmediate();
  enter(h, 'purpose', '  Synthetic   inventory  ');
  enter(h, 'requested_amount', '1e3');
  submit(h);
  await setImmediate();
  assert.equal(body(h).information.request.purpose, '  Synthetic   inventory  ');
  assert.equal(body(h).information.request.requested_amount, '1e3');
  assert.equal(h.saved.length, 1);
});

test('changed current CIF requires an explicit source choice before appending', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  h.context.cif_version_id = OTHER_CIF;
  h.context.cif_version_number = 5;
  mount(h);
  await setImmediate();
  assert.match(h.root.textContent, /Saved application uses CIF version 4/);
  assert.match(h.root.textContent, /Use current CIF version 5 for this new application version/);
  assert.equal(Boolean(field(h, 'use_current_cif').checked), false);
  assert.equal(button(h, 'Save application').disabled, true);
  submit(h);
  assert.equal(h.calls.length, 1);
  field(h, 'use_current_cif').checked = true;
  fire(field(h, 'use_current_cif'), 'change');
  assert.equal(button(h, 'Save application').disabled, false);
  submit(h);
  await setImmediate();
  assert.equal(body(h).cif_version_id, OTHER_CIF);
  assert.equal(h.saved.length, 1);
});

test('empty active catalog preserves an unavailable saved product without a raw ID label', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  h.context.loan_types = [];
  mount(h);
  await setImmediate();
  assert.equal(field(h, 'requested_loan_type_id').value, PRODUCT);
  assert.match(h.root.textContent, /Previously selected product \(unavailable in current catalog\)/);
  assert.equal(h.root.textContent.includes(PRODUCT), false);
  submit(h);
  await setImmediate();
  assert.equal(body(h).information.request.requested_loan_type_id, PRODUCT);
});

test('add/remove obligation rows preserves other edits and never silently deletes conflicting debt facts', async () => {
  const mount = await loadMount();
  const h = harness();
  mount(h);
  await setImmediate();
  enter(h, 'purpose', 'Unsubmitted purpose');
  fire(button(h, 'Add obligation'), 'click');
  enter(h, 'obligation_0_creditor', 'First creditor');
  fire(button(h, 'Add obligation'), 'click');
  enter(h, 'obligation_1_creditor', 'Second creditor');
  enter(h, 'has_existing_obligations', 'false');
  submit(h);
  assert.equal(h.calls.length, 1);
  assert.equal(field(h, 'obligation_1_creditor').value, 'Second creditor');
  assert.match(h.root.textContent, /Remove the obligation rows/i);
  fire(button(h, 'Remove obligation 1'), 'click');
  assert.equal(field(h, 'obligation_0_creditor').value, 'Second creditor');
  assert.equal(field(h, 'purpose').value, 'Unsubmitted purpose');
  enter(h, 'has_existing_obligations', '');
  submit(h);
  await setImmediate();
  assert.equal(body(h).information.repayment.has_existing_obligations, null);
  assert.deepEqual(body(h).information.repayment.obligations, [{ creditor: 'Second creditor', outstanding_balance: null, periodic_payment_amount: null, payment_frequency: null, notes: null }]);
});

for (const [role, permissions] of [['collector', [PERMISSION]], ['client', [PERMISSION]], ['employee', []], ['management', [`${PERMISSION}.extra`]]]) {
  test(`${role}/${permissions}: denied mount has no form or request`, async () => {
    const mount = await loadMount();
    const h = harness({ role, permissions });
    mount(h);
    assert.equal(h.calls.length, 0);
    assert.equal(h.root.querySelector('form'), null);
  });
}

for (const [label, change] of [
  ['client mismatch', (value) => { value.client_id = APPLICATION; }],
  ['invalid CIF', (value) => { value.cif_version_id = 'not-a-uuid'; }],
  ['invalid CIF version', (value) => { value.cif_version_number = '4'; }],
  ['invalid product', (value) => { value.loan_types[0].name = {}; }],
  ['duplicate product', (value) => { value.loan_types.push({ ...value.loan_types[0] }); }],
]) {
  test(`context ${label} fails closed without a save action`, async () => {
    const mount = await loadMount();
    const h = harness();
    change(h.context);
    mount(h);
    await setImmediate();
    assert.equal(h.root.querySelector('form'), null);
    assert.ok(button(h, 'Reload application'));
    assert.equal(h.calls.length, 1);
  });
}

for (const [label, change] of [
  ['client mismatch', (value) => { value.client_id = APPLICATION; }],
  ['reference case mismatch', (value) => { value.application_reference = REFERENCE.toLowerCase(); }],
  ['numeric money', (value) => { value.information.request.requested_amount = 100; }],
  ['invalid version', (value) => { value.version_number = '9'; }],
]) {
  test(`untrusted append review ${label} cannot open an editor`, async () => {
    const mount = await loadMount();
    const h = harness({ append: true });
    change(h.review);
    mount(h);
    await setImmediate();
    assert.equal(h.calls.length, 0);
    assert.equal(h.root.querySelector('form'), null);
  });
}

for (const status of [400, 422]) {
  test(`${status} retains edits and allows a deliberate corrected submission`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.fetch = (_, init) => Promise.resolve(response(init.method === 'GET' ? h.context : { detail: '<img src=x onerror=alert(1)> Invalid amount' }, init.method === 'GET' ? 200 : status));
    mount(h);
    await setImmediate();
    enter(h, 'requested_amount', '12.345');
    submit(h);
    await setImmediate();
    assert.equal(field(h, 'requested_amount').value, '12.345');
    assert.equal(button(h, 'Save application').disabled, false);
    assert.equal(h.root.querySelector('img'), null);
    assert.match(h.root.innerHTML, /&lt;img/);
    enter(h, 'requested_amount', '12.34');
    h.fetch = null;
    submit(h);
    await setImmediate();
    assert.equal(h.calls.length, 3);
    assert.equal(h.saved.length, 1);
  });
}

for (const status of [409, 500, 'network']) {
  test(`${status} locks Save and reload explicitly closes without another write`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.fetch = (_, init) => init.method === 'GET' ? Promise.resolve(response(h.context))
      : status === 'network' ? Promise.reject(new Error('connection lost'))
        : Promise.resolve(response({ detail: 'Cannot verify this save.' }, status));
    mount(h);
    await setImmediate();
    enter(h, 'purpose', 'Private draft purpose');
    const purpose = field(h, 'purpose');
    submit(h);
    await setImmediate();
    assert.equal(button(h, 'Save application').disabled, true);
    assert.ok(button(h, 'Reload application'));
    submit(h);
    assert.equal(h.calls.length, 2);
    fire(button(h, 'Reload application'), 'click');
    assert.deepEqual(h.cancelled, [{ reload: true }]);
    assert.equal(h.root.innerHTML, '');
    assert.equal(purpose.value, '');
    assert.equal(h.calls.length, 2);
  });
}

for (const [label, change] of [
  ['Client', (value) => { value.client_id = APPLICATION; }],
  ['reference', (value) => { value.application_reference = REFERENCE.toLowerCase(); }],
  ['source CIF', (value) => { value.cif_version_id = OTHER_CIF; }],
  ['application', (value) => { value.application_id = CIF; }],
  ['version', (value) => { value.version_number = 12; }],
  ['scope', (value) => { value.review_scope = 'approved'; }],
  ['numeric money', (value) => { value.information.request.requested_amount = 100; }],
  ['stale unchanged version', (value) => { value.version_number = 9; value.application_version_id = VERSION; }],
]) {
  test(`unverified save ${label} blocks retry and never reports success`, async () => {
    const mount = await loadMount();
    const h = harness({ append: true });
    const saved = { ...review(), version_number: 10, application_version_id: NEXT_VERSION };
    change(saved);
    h.fetch = (_, init) => Promise.resolve(response(init.method === 'GET' ? h.context : saved));
    mount(h);
    await setImmediate();
    enter(h, 'purpose', 'Changed purpose');
    submit(h);
    await setImmediate();
    assert.equal(h.saved.length, 0);
    assert.equal(button(h, 'Save application').disabled, true);
    assert.ok(button(h, 'Reload application'));
    submit(h);
    assert.equal(h.calls.length, 2);
  });
}

test('pending Save sends only once and Cancel clears detached inputs and suppresses late success', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  const pending = deferred();
  h.fetch = (_, init) => init.method === 'GET' ? Promise.resolve(response(h.context)) : pending.promise;
  mount(h);
  await setImmediate();
  const form = h.root.querySelector('form');
  const purpose = field(h, 'purpose');
  submit(h);
  submit(h);
  fire(button(h, 'Add obligation'), 'click');
  assert.equal(h.calls.length, 2);
  assert.equal(button(h, 'Save application').disabled, true);
  fire(button(h, 'Cancel'), 'click');
  assert.deepEqual(h.cancelled, [{ reload: true }]);
  assert.equal(purpose.value, '');
  fire(form, 'submit');
  pending.resolve(response({ ...review(), version_number: 10, application_version_id: NEXT_VERSION }));
  await setImmediate();
  assert.equal(h.root.innerHTML, '');
  assert.equal(h.saved.length, 0);
  assert.equal(h.calls.length, 2);
});

for (const attempted of [false, true]) {
  test(`Cancel ${attempted ? 'after an uncertain save reconciles' : 'before a save exits'} without a write replay`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.fetch = (_, init) => init.method === 'GET' ? Promise.resolve(response(h.context)) : Promise.reject(new Error('Connection lost'));
    mount(h); await setImmediate();
    enter(h, 'purpose', 'Private draft');
    if (attempted) { submit(h); await setImmediate(); }
    fire(button(h, 'Cancel'), 'click');
    assert.deepEqual(h.cancelled, [{ reload: attempted }]);
    assert.equal(h.root.innerHTML, '');
    assert.equal(h.calls.length, attempted ? 2 : 1);
  });
}

for (const status of [401, 403]) {
  test(`${status} on Save clears private values and removes all mutation actions`, async () => {
    const mount = await loadMount();
    const h = harness({ append: true });
    h.fetch = (_, init) => Promise.resolve(response(init.method === 'GET' ? h.context : { detail: 'Office access required.' }, init.method === 'GET' ? 200 : status));
    mount(h);
    await setImmediate();
    const purpose = field(h, 'purpose');
    const form = h.root.querySelector('form');
    submit(h);
    await setImmediate();
    assert.equal(purpose.value, '');
    assert.equal(h.root.querySelector('form'), null);
    assert.equal(button(h, 'Reload application'), undefined);
    fire(form, 'submit');
    assert.equal(h.calls.length, 2);
    assert.equal(h.saved.length, 0);
  });
}

for (const phase of ['context', 'save']) {
  for (const action of ['abort', 'dispose', 'remount']) {
    test(`${action} during ${phase} invalidates late responses and callbacks`, async () => {
      const mount = await loadMount();
      const h = harness({ append: true });
      const pending = deferred();
      h.fetch = (_, init) => (phase === 'context' || init.method === 'POST') ? pending.promise : Promise.resolve(response(h.context));
      const dispose = mount(h);
      if (phase === 'save') { await setImmediate(); submit(h); }
      const controls = [...h.root.querySelectorAll('input'), ...h.root.querySelectorAll('textarea'), ...h.root.querySelectorAll('select')];
      if (action === 'abort') h.controller.abort();
      if (action === 'dispose') dispose();
      if (action === 'remount') mount({ ...h, session: { user: { role: 'client' }, permissions: [PERMISSION] } });
      const clearedMarkup = h.root.innerHTML;
      pending.resolve(response(phase === 'context' ? h.context : { ...review(), version_number: 10, application_version_id: NEXT_VERSION }));
      await setImmediate();
      assert.equal(h.root.innerHTML, clearedMarkup);
      assert.equal(h.saved.length, 0);
      assert.equal(h.cancelled.length, 0);
      for (const control of controls) assert.equal(control.value, '');
    });
  }
}

test('already aborted signal makes no request and renders nothing', async () => {
  const mount = await loadMount();
  const h = harness();
  h.controller.abort();
  mount(h);
  assert.equal(h.calls.length, 0);
  assert.equal(h.root.innerHTML, '');
});

test('reference, product labels and prefill text cannot inject markup', async () => {
  const mount = await loadMount();
  const h = harness({ append: true });
  h.applicationReference = '<img src=x onerror=alert(1)>';
  h.review.application_reference = h.applicationReference;
  h.review.information.request.purpose = '<script>alert(2)</script>';
  h.context.loan_types[0].name = '<svg onload=alert(3)>';
  mount(h);
  await setImmediate();
  assert.equal(h.root.querySelector('img'), null);
  assert.equal(h.root.querySelector('script'), null);
  assert.equal(h.root.querySelector('svg'), null);
  assert.equal(field(h, 'purpose').value, '<script>alert(2)</script>');
  assert.match(h.root.innerHTML, /&lt;img/);
  assert.match(h.root.innerHTML, /&lt;svg/);
});
