import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { SpinaApi } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/office-application-review.js', import.meta.url);
const CLIENT_ID = '11111111-1111-4111-8111-111111111111';
const APPLICATION_ID = '22222222-2222-4222-8222-222222222222';
const VERSION_ID = '33333333-3333-4333-8333-333333333333';
const CIF_ID = '44444444-4444-4444-8444-444444444444';
const PRODUCT_ID = '55555555-5555-4555-8555-555555555555';
const PERMISSION = 'client_onboarding.requirement.review';
const INTAKE = 'APP-2026-000017';
const APPLICATION = 'Loan / MixedCase-017';
const LOOKUP = '/api/v1/management/onboarding/applicants/by-reference/';
const SUMMARY = `/api/v1/management/clients/${CLIENT_ID}/loan-applications/by-reference/`;

async function loadMount() {
  assert.equal(existsSync(moduleUrl), true, 'Office application review is not implemented');
  const { mountOfficeApplicationReview } = await import(moduleUrl.href);
  assert.equal(typeof mountOfficeApplicationReview, 'function');
  return mountOfficeApplicationReview;
}

function review() {
  return {
    client_id: CLIENT_ID, application_id: APPLICATION_ID,
    application_version_id: VERSION_ID, application_reference: APPLICATION,
    cif_version_id: CIF_ID, cif_version_number: 4, version_number: 9,
    recorded_at: '2026-09-19T02:03:04Z', review_scope: 'loan_application_information_only',
    requested_loan_type_name: 'Current catalog product', missing_fields: [],
    information: {
      request: {
        requested_loan_type_id: PRODUCT_ID, purpose: 'Synthetic inventory purchase',
        requested_amount: '123456789012345678901234567890.12',
        requested_payment_arrangement: 'Weekly in office', requested_term: 'Six weeks',
        preferred_first_payment_date: '2026-10-02',
      },
      repayment: {
        repayment_source: 'Synthetic shop income', source_details: 'Synthetic sales receipts',
        monthly_gross_income: '1.234567890123456789E+40', monthly_net_income: '-12345678901234567890.01',
        has_existing_obligations: true,
        obligations: [
          { creditor: 'Synthetic Creditor One', outstanding_balance: '0.00', periodic_payment_amount: '1500.25', payment_frequency: 'Monthly', notes: 'Synthetic first debt note' },
          { creditor: 'Synthetic Creditor Two', outstanding_balance: '9.99E+30', periodic_payment_amount: null, payment_frequency: 'Weekly', notes: null },
        ],
      },
    },
  };
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

function harness({ role = 'employee', permissions = [PERMISSION] } = {}) {
  const h = { root: new Element(), calls: [], review: review(), fetch: null, controller: new AbortController() };
  h.session = { user: { role, roles: [role] }, permissions, access_token: 'synthetic-token' };
  h.signal = h.controller.signal;
  h.api = new SpinaApi({
    sessionStore: { load: () => h.session, deviceId: () => 'synthetic-office-device', clear() {} },
    fetchImpl(path, init) {
      h.calls.push({ path, init });
      return h.fetch ? h.fetch(path, init) : Promise.resolve(response(path.startsWith(LOOKUP)
        ? { application_reference: INTAKE, client_id: CLIENT_ID } : h.review));
    },
  });
  return h;
}

function input(h, name) { return h.root.querySelector(`[name="${name}"]`); }
function button(h, label) { return h.root.querySelectorAll('button').find((element) => element.textContent === label); }
function enter(h, name, value, event = 'input') {
  input(h, name).value = value;
  fire(input(h, name), event);
}
function submit(h, intake = INTAKE, application = APPLICATION) {
  enter(h, 'intakeReference', intake);
  enter(h, 'applicationReference', application);
  assert.equal(fire(h.root.querySelector('form'), 'submit').defaultPrevented, true);
}
function detail(h, label) {
  const item = h.root.querySelectorAll('.detail-item').find((element) => element.querySelector('span')?.textContent === label);
  assert.ok(item, `Missing rendered field: ${label}`);
  return item.querySelector('strong').textContent;
}
function noFacts(h) {
  assert.doesNotMatch(h.root.textContent, /Synthetic inventory purchase|Synthetic shop income|Synthetic Creditor/);
}

for (const role of ['employee', ' Management ']) {
  test(`${role}: two authenticated GETs show every saved application fact without current CIF or UUID content`, async () => {
    const mount = await loadMount();
    const h = harness({ role });
    const dispose = mount(h);
    assert.equal(typeof dispose, 'function');
    assert.equal(h.calls.length, 0);
    assert.equal(h.root.querySelectorAll('input').length, 2);
    assert.match(h.root.textContent, /Office intake reference/);
    assert.match(h.root.textContent, /Loan application reference/);
    assert.ok(button(h, 'Open application review'));
    assert.ok(button(h, 'Clear'));
    submit(h, ` ${INTAKE.toLowerCase()} `, ` ${APPLICATION} `);
    await setImmediate();
    assert.deepEqual(h.calls.map(({ path }) => path), [
      `${LOOKUP}${INTAKE.toLowerCase()}/cif-client`,
      `${SUMMARY}${encodeURIComponent(APPLICATION)}/review-summary`,
    ]);
    for (const { init } of h.calls) {
      assert.equal(init.method, 'GET');
      assert.equal(init.body, undefined);
      assert.equal(init.headers.Authorization, 'Bearer synthetic-token');
      assert.equal(init.headers['X-Device-Id'], 'synthetic-office-device');
    }
    for (const value of [APPLICATION, 'Current catalog product', 'Synthetic inventory purchase', 'Weekly in office', 'Six weeks', '2026-10-02', 'Synthetic shop income', 'Synthetic sales receipts', 'Synthetic Creditor One', 'Synthetic Creditor Two', 'Monthly', 'Weekly', 'Synthetic first debt note']) assert.ok(h.root.textContent.includes(value), value);
    for (const amount of ['123456789012345678901234567890.12', '1.234567890123456789E+40', '-12345678901234567890.01', '0.00', '1500.25', '9.99E+30']) assert.ok(h.root.textContent.includes(`PHP ${amount}`), amount);
    assert.equal(detail(h, 'Application version'), '9');
    assert.equal(detail(h, 'Linked CIF version'), '4');
    assert.match(detail(h, 'Recorded at'), /2026-09-19/);
    assert.equal(detail(h, 'Existing obligations'), 'Yes');
    assert.match(h.root.textContent, /Requested information only; approval and release are separate/);
    assert.match(h.root.textContent, /request and repayment/i);
    assert.match(h.root.textContent, /does not assess whether the full application is complete or ready for approval/i);
    for (const id of [CLIENT_ID, APPLICATION_ID, VERSION_ID, CIF_ID, PRODUCT_ID]) assert.equal(h.root.innerHTML.includes(id), false);
    dispose();
    assert.equal(h.root.innerHTML, '');
  });
}

for (const [role, permissions] of [
  ['collector', [PERMISSION]], ['client', [PERMISSION]],
  ['employee', []], ['management', [`${PERMISSION}.extra`]],
]) {
  test(`${role}/${permissions.join(',')}: unauthorized surface has no form or requests`, async () => {
    const mount = await loadMount();
    const h = harness({ role, permissions });
    mount(h);
    assert.equal(h.root.querySelector('form'), null);
    assert.equal(h.calls.length, 0);
  });
}

test('empty references fail before lookup and do not preserve old information', async () => {
  const mount = await loadMount();
  const h = harness();
  mount(h);
  for (const references of [[' ', APPLICATION], [INTAKE, ' ']]) {
    submit(h, ...references);
    await setImmediate();
    assert.equal(h.calls.length, 0);
    assert.ok(h.root.querySelector('[role="alert"]'));
    noFacts(h);
  }
});

test('null facts, zero money and a false obligations declaration remain distinct', async () => {
  const mount = await loadMount();
  const h = harness();
  h.review.information.request = Object.fromEntries(Object.keys(h.review.information.request).map((key) => [key, null]));
  h.review.requested_loan_type_name = null;
  h.review.information.repayment = { repayment_source: null, source_details: null, monthly_gross_income: '0.00', monthly_net_income: null, has_existing_obligations: false, obligations: [] };
  h.review.missing_fields = ['request.purpose', 'request.requested_amount', 'repayment.repayment_source'];
  mount(h);
  submit(h);
  await setImmediate();
  assert.equal(detail(h, 'Requested product (current catalog label)'), 'Not provided');
  assert.equal(detail(h, 'Requested amount'), 'Not provided');
  assert.equal(detail(h, 'Monthly gross income'), 'PHP 0.00');
  assert.equal(detail(h, 'Monthly net income'), 'Not provided');
  assert.equal(detail(h, 'Existing obligations'), 'No');
  assert.match(h.root.textContent, /Missing request and repayment facts/);
  assert.doesNotMatch(h.root.textContent, /request\.purpose|repayment\.repayment_source/);
  h.review.information.repayment.has_existing_obligations = null;
  submit(h);
  await setImmediate();
  assert.equal(detail(h, 'Existing obligations'), 'Not provided');
});

test('missing catalog label and obligation fields remain readable without exposing IDs or readiness claims', async () => {
  const mount = await loadMount();
  const h = harness();
  h.review.requested_loan_type_name = null;
  h.review.missing_fields = ['repayment.obligations[1].periodic_payment_amount'];
  mount(h);
  submit(h);
  await setImmediate();
  assert.equal(detail(h, 'Requested product (current catalog label)'), 'Unavailable');
  assert.match(h.root.textContent, /Obligation 2: Periodic payment amount/);
  assert.doesNotMatch(h.root.textContent, /obligations\[|approved|confirmed|application is ready for approval/i);
});

for (const [reason, mutate] of [
  ['different Client', (r) => { r.client_id = APPLICATION_ID; }],
  ['differently cased reference', (r) => { r.application_reference = APPLICATION.toLowerCase(); }],
  ['missing application identity', (r) => { delete r.application_id; }],
  ['bad saved version identity', (r) => { r.application_version_id = 'bad'; }],
  ['invalid linked CIF version', (r) => { r.cif_version_number = 0; }],
  ['wrong review scope', (r) => { r.review_scope = 'cif_information_only'; }],
  ['numeric amount', (r) => { r.information.request.requested_amount = 1200; }],
  ['nondecimal money', (r) => { r.information.repayment.monthly_net_income = 'NaN'; }],
  ['string obligation boolean', (r) => { r.information.repayment.has_existing_obligations = 'false'; }],
  ['nonarray obligations', (r) => { r.information.repayment.obligations = {}; }],
  ['bad obligation value', (r) => { r.information.repayment.obligations[0].creditor = 7; }],
  ['missing nullable field', (r) => { delete r.information.request.purpose; }],
  ['bad product label', (r) => { r.requested_loan_type_name = {}; }],
  ['invalid saved timestamp', (r) => { r.recorded_at = 'yesterday'; }],
  ['unknown missing-field scope', (r) => { r.missing_fields = ['privacy.status']; }],
]) {
  test(`${reason} fails closed before any saved facts are displayed`, async () => {
    const mount = await loadMount();
    const h = harness();
    mutate(h.review);
    mount(h);
    submit(h);
    await setImmediate();
    assert.equal(h.calls.length, 2);
    noFacts(h);
    assert.ok(h.root.querySelector('[role="alert"]'));
  });
}

test('a mismatched office reference prevents the application query', async () => {
  const mount = await loadMount();
  const h = harness();
  h.fetch = async () => response({ application_reference: 'OTHER-INTAKE', client_id: CLIENT_ID });
  mount(h);
  submit(h);
  await setImmediate();
  assert.equal(h.calls.length, 1);
  noFacts(h);
  assert.ok(h.root.querySelector('[role="alert"]'));
});

test('references, facts, obligation notes and server errors are escaped', async () => {
  const mount = await loadMount();
  const h = harness();
  const hostile = '<img src=x onerror=alert(1)> & / exact';
  h.review.application_reference = hostile;
  h.review.requested_loan_type_name = hostile;
  h.review.information.request.purpose = hostile;
  h.review.information.repayment.obligations[0].notes = hostile;
  mount(h);
  submit(h, INTAKE, hostile);
  await setImmediate();
  assert.equal(h.calls[1].path, `${SUMMARY}${encodeURIComponent(hostile)}/review-summary`);
  assert.doesNotMatch(h.root.innerHTML, /<img\b/i);
  assert.match(h.root.innerHTML, /&lt;img/);
  h.fetch = async () => response({ detail: hostile }, 403);
  submit(h);
  await setImmediate();
  assert.doesNotMatch(h.root.innerHTML, /<img\b/i);
  assert.match(h.root.innerHTML, /&lt;img/);
  noFacts(h);
});

for (const stage of ['lookup', 'summary']) {
  for (const action of ['intake input', 'application change', 'Clear', 'dispose', 'abort', 'remount']) {
    test(`${action} clears visible facts and invalidates a pending ${stage}`, async () => {
      const mount = await loadMount();
      const h = harness();
      const dispose = mount(h);
      submit(h);
      await setImmediate();
      assert.match(h.root.textContent, /Synthetic inventory purchase/);
      const pending = deferred();
      h.fetch = (path) => (stage === 'lookup' ? path.startsWith(LOOKUP) : path.startsWith(SUMMARY))
        ? pending.promise : Promise.resolve(response({ application_reference: INTAKE, client_id: CLIENT_ID }));
      submit(h);
      noFacts(h);
      await setImmediate();
      const oldForm = h.root.querySelector('form');
      if (action === 'intake input') enter(h, 'intakeReference', 'OTHER');
      else if (action === 'application change') enter(h, 'applicationReference', 'OTHER', 'change');
      else if (action === 'Clear') fire(button(h, 'Clear'), 'click');
      else if (action === 'dispose') dispose();
      else if (action === 'abort') h.controller.abort();
      else mount(h);
      const cleared = h.root.innerHTML;
      const count = h.calls.length;
      pending.resolve(response(stage === 'lookup' ? { application_reference: INTAKE, client_id: CLIENT_ID } : h.review));
      await setImmediate();
      assert.equal(h.root.innerHTML, cleared);
      assert.equal(h.calls.length, count);
      noFacts(h);
      if (['dispose', 'abort', 'remount'].includes(action)) {
        fire(oldForm, 'submit');
        await setImmediate();
        assert.equal(h.calls.length, count);
      }
    });
  }
}

for (const outcome of ['success', 'error']) {
  test(`a late old summary ${outcome} cannot replace the newer application`, async () => {
    const mount = await loadMount();
    const h = harness();
    const pending = deferred();
    const newReference = 'NewExactReference';
    h.fetch = (path) => {
      if (path.startsWith(LOOKUP)) return Promise.resolve(response({ application_reference: INTAKE, client_id: CLIENT_ID }));
      if (path.includes(encodeURIComponent(APPLICATION))) return pending.promise;
      return Promise.resolve(response({ ...h.review, application_reference: newReference }));
    };
    mount(h);
    submit(h);
    await setImmediate();
    submit(h, INTAKE, newReference);
    await setImmediate();
    const newer = h.root.innerHTML;
    assert.ok(newer.includes(newReference));
    if (outcome === 'success') pending.resolve(response(h.review));
    else pending.reject(new Error('Old private response failed'));
    await setImmediate();
    assert.equal(h.root.innerHTML, newer);
  });
}

test('already aborted mounts are empty and independent roots do not invalidate each other', async () => {
  const mount = await loadMount();
  const aborted = harness();
  aborted.controller.abort();
  mount(aborted);
  assert.equal(aborted.root.innerHTML, '');
  assert.equal(aborted.calls.length, 0);
  const first = harness();
  const second = harness();
  const dispose = mount(first);
  mount(second);
  submit(first);
  submit(second);
  await setImmediate();
  dispose();
  assert.equal(first.root.innerHTML, '');
  assert.match(second.root.textContent, /Synthetic inventory purchase/);
});
