import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { SpinaApi } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/office-cif-selection.js', import.meta.url);
const CLIENT_A = '11111111-1111-4111-8111-111111111111';
const CLIENT_B = '22222222-2222-4222-8222-222222222222';
const CIF_ID = '33333333-3333-4333-8333-333333333333';
const PERMISSION = 'client_onboarding.requirement.review';
const REFERENCE_A = 'APP-2026-000001';
const REFERENCE_B = 'APP-2026-000002';
const LOOKUP = '/api/v1/management/onboarding/applicants/by-reference/';
const OLD_PII = 'Previous Applicant Private Address';

async function loadMount() {
  assert.equal(existsSync(moduleUrl), true, 'Office CIF selection is not implemented');
  const { mountOfficeCifSelection } = await import(moduleUrl.href);
  assert.equal(typeof mountOfficeCifSelection, 'function');
  return mountOfficeCifSelection;
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function review(clientId = CLIENT_A, name = 'Synthetic Applicant Alpha') {
  return {
    client_id: clientId, cif_version_id: CIF_ID, version_number: 1,
    status: 'draft', liveness_status: 'pending', review_scope: 'cif_information_only',
    full_name: name, phone_number: '09170000001', email: 'alpha@example.test',
    present_address: '17 Synthetic Test Street',
  };
}

function selection(reference = REFERENCE_A, clientId = CLIENT_A) {
  return { application_reference: reference, client_id: clientId };
}

function response(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
}

function harness({ role = 'employee', permissions = [PERMISSION], fetchImpl } = {}) {
  const session = { user: { role, roles: [role] }, permissions, access_token: 'synthetic-token' };
  const requests = [];
  const writes = [];
  const api = new SpinaApi({
    sessionStore: {
      load: () => session,
      deviceId: () => 'synthetic-office-device',
      clear: () => writes.push('clear'),
      save: () => writes.push('save'),
    },
    fetchImpl: (path, init) => {
      requests.push({ path, init });
      return fetchImpl ? fetchImpl(path, init) : Promise.resolve(response(
        path.startsWith(LOOKUP) ? selection() : review(),
      ));
    },
  });
  const root = new Element();
  root.innerHTML = OLD_PII;
  return { root, api, session, requests, writes };
}

function enter(h, value, event = 'input') {
  const input = h.root.querySelector('input');
  input.value = value;
  fire(input, event);
}

function submit(h) {
  const event = fire(h.root.querySelector('form'), 'submit');
  assert.equal(event.defaultPrevented, true);
}

function assertNoPii(root) {
  assert.doesNotMatch(root.innerHTML, /Previous Applicant Private Address|Synthetic Applicant Alpha|17 Synthetic Test Street|alpha@example\.test/);
}

for (const role of ['employee', ' Management ']) {
  test(`${role} can open the exact office reference through two authenticated GETs`, async () => {
    const mount = await loadMount();
    const h = harness({ role });
    const dispose = mount(h);
    assert.equal(typeof dispose, 'function');
    assert.equal(h.requests.length, 0);
    assertNoPii(h.root);
    assert.equal(h.root.querySelectorAll('input').length, 1);
    assert.match(h.root.querySelector('label').textContent, /Office intake reference/);
    assert.match(h.root.querySelector('button[type="submit"]').textContent, /Open CIF review/);
    assert.match(h.root.querySelector('button[type="button"]').textContent, /Clear/);
    assert.ok(h.root.querySelector('[role="status"]'));
    enter(h, `  ${REFERENCE_A.toLowerCase()}  `);
    submit(h);
    await setImmediate();

    assert.deepEqual(h.requests.map(({ path }) => path), [
      `${LOOKUP}${REFERENCE_A.toLowerCase()}/cif-client`,
      `/api/v1/management/clients/${CLIENT_A}/cif/review-summary`,
    ]);
    for (const { init } of h.requests) {
      assert.equal(init.method, 'GET');
      assert.equal(init.body, undefined);
      assert.equal(init.headers.Authorization, 'Bearer synthetic-token');
      assert.equal(init.headers['X-Device-Id'], 'synthetic-office-device');
    }
    assert.match(h.root.textContent, /Synthetic Applicant Alpha/);
    assert.deepEqual(h.writes, []);
    dispose();
    assert.equal(h.root.innerHTML, '');
  });
}

for (const [role, permissions] of [
  ['collector', [PERMISSION]], ['client', [PERMISSION]], ['unknown', [PERMISSION]],
  ['employee', []], ['management', [`${PERMISSION}.extra`]],
]) {
  test(`${role}/${permissions.join(',')} has no selection form without exact authority`, async () => {
    const mount = await loadMount();
    const h = harness({ role, permissions });
    const dispose = mount(h);
    assert.equal(typeof dispose, 'function');
    assert.equal(h.root.querySelector('form'), null);
    assertNoPii(h.root);
    assert.equal(h.requests.length, 0);
    dispose();
  });
}

test('empty input reports an accessible error without fetching', async () => {
  const mount = await loadMount();
  const h = harness();
  mount(h);
  enter(h, ' \t ');
  submit(h);
  await setImmediate();
  assert.equal(h.requests.length, 0);
  assert.ok(h.root.querySelector('[role="alert"]'));
  assert.match(h.root.textContent, /reference.*required|enter.*reference/i);
});

test('arbitrary slash-bearing references are encoded and never treated as markup', async () => {
  const mount = await loadMount();
  const reference = 'Office / <img src=x onerror=alert(1)> ? # &';
  const h = harness({ fetchImpl: async (path) => response(path.startsWith(LOOKUP)
    ? selection(reference) : review(CLIENT_A, '<svg onload=alert(2)> Borrower')) });
  mount(h);
  enter(h, ` ${reference} `);
  submit(h);
  await setImmediate();
  assert.equal(h.requests[0].path, `${LOOKUP}${encodeURIComponent(reference)}/cif-client`);
  assert.equal(h.requests.length, 2);
  assert.doesNotMatch(h.root.innerHTML, /<(?:img|svg|script)\b/i);
  assert.match(h.root.innerHTML, /&lt;svg onload=alert\(2\)&gt; Borrower/);
});

for (const [reason, payload] of [
  ['missing response', null], ['wrong reference', selection(REFERENCE_B)],
  ['missing reference', { client_id: CLIENT_A }],
  ['non-text reference', selection(17)],
  ['bad UUID', selection(REFERENCE_A, '../other?private=true')],
  ['missing UUID', { application_reference: REFERENCE_A }],
]) {
  test(`${reason} never opens the CIF summary`, async () => {
    const mount = await loadMount();
    const h = harness({ fetchImpl: async () => response(payload) });
    mount(h);
    enter(h, REFERENCE_A);
    submit(h);
    await setImmediate();
    assert.equal(h.requests.length, 1);
    assertNoPii(h.root);
    assert.ok(h.root.querySelector('[role="alert"]'));
    assert.match(h.root.textContent, /invalid|does not match|unavailable/i);
  });
}

test('lookup denial is escaped and cannot restore previous applicant information', async () => {
  const mount = await loadMount();
  const h = harness({ fetchImpl: async () => response({ detail: '<img src=x onerror=alert(1)> Denied' }, 403) });
  mount(h);
  enter(h, REFERENCE_A);
  submit(h);
  await setImmediate();
  assertNoPii(h.root);
  assert.doesNotMatch(h.root.innerHTML, /<img\b/i);
  assert.match(h.root.innerHTML, /&lt;img/);
  assert.ok(h.root.querySelector('[role="alert"]'));
});

for (const outcome of ['success', 'error']) {
  test(`late lookup ${outcome} cannot replace the newer selection`, async () => {
    const mount = await loadMount();
    const pending = deferred();
    const h = harness({ fetchImpl: (path) => {
      if (path.includes(REFERENCE_A)) return pending.promise;
      return Promise.resolve(response(path.startsWith(LOOKUP)
        ? selection(REFERENCE_B, CLIENT_B) : review(CLIENT_B, 'Synthetic Applicant Beta')));
    } });
    mount(h);
    enter(h, REFERENCE_A);
    submit(h);
    assert.equal(h.root.querySelector('input').disabled, false);
    enter(h, REFERENCE_B);
    submit(h);
    await setImmediate();
    const newer = h.root.innerHTML;
    if (outcome === 'success') pending.resolve(response(selection()));
    else pending.reject(new Error('Old lookup failed'));
    await setImmediate();
    assert.equal(h.root.innerHTML, newer);
    assert.match(h.root.textContent, /Synthetic Applicant Beta/);
    assert.equal(h.requests.length, 3);
  });
}

for (const stage of ['lookup', 'summary']) {
  for (const action of ['input', 'change', 'clear', 'dispose', 'abort']) {
    test(`${action} immediately clears review and suppresses a pending ${stage}`, async () => {
      const mount = await loadMount();
      const pending = deferred();
      const controller = new AbortController();
      let pendingEnabled = false;
      const h = harness({ fetchImpl: (path) => {
        if (pendingEnabled && (stage === 'lookup' ? path.startsWith(LOOKUP) : !path.startsWith(LOOKUP))) return pending.promise;
        return Promise.resolve(response(path.startsWith(LOOKUP) ? selection() : review()));
      } });
      const dispose = mount({ ...h, signal: controller.signal });
      enter(h, REFERENCE_A);
      submit(h);
      await setImmediate();
      assert.match(h.root.textContent, /Synthetic Applicant Alpha/);
      pendingEnabled = true;
      submit(h);
      assertNoPii(h.root);
      await setImmediate();
      const oldInput = h.root.querySelector('input');
      const oldForm = h.root.querySelector('form');
      if (action === 'input' || action === 'change') enter(h, REFERENCE_B, action);
      else if (action === 'clear') fire(h.root.querySelector('button[type="button"]'), 'click');
      else if (action === 'dispose') dispose();
      else controller.abort();
      assertNoPii(h.root);
      const cleared = h.root.innerHTML;
      const requestCount = h.requests.length;
      pending.resolve(response(stage === 'lookup' ? selection() : review()));
      await setImmediate();
      assert.equal(h.root.innerHTML, cleared);
      assert.equal(h.requests.length, requestCount);
      if (['dispose', 'abort'].includes(action)) {
        assert.equal(h.root.innerHTML, '');
        oldInput.value = REFERENCE_A;
        fire(oldInput, 'input');
        fire(oldForm, 'submit');
        await setImmediate();
        assert.equal(h.requests.length, requestCount);
      } else if (action === 'clear') assert.equal(oldInput.value, '');
    });
  }
}

test('an already aborted mount is empty and makes no request', async () => {
  const mount = await loadMount();
  const h = harness();
  const controller = new AbortController();
  controller.abort();
  const dispose = mount({ ...h, signal: controller.signal });
  assert.equal(typeof dispose, 'function');
  assert.equal(h.root.innerHTML, '');
  assert.equal(h.requests.length, 0);
  dispose();
});

test('repeated mount invalidates detached listeners and pending summary; old dispose cannot clear new UI', async () => {
  const mount = await loadMount();
  const pending = deferred();
  const h = harness({ fetchImpl: (path) => path.startsWith(LOOKUP)
    ? Promise.resolve(response(selection())) : pending.promise });
  const oldDispose = mount(h);
  enter(h, REFERENCE_A);
  submit(h);
  await setImmediate();
  const oldForm = h.root.querySelector('form');
  const newDispose = mount(h);
  const remounted = h.root.innerHTML;
  oldDispose();
  fire(oldForm, 'submit');
  pending.resolve(response(review()));
  await setImmediate();
  assert.equal(h.root.innerHTML, remounted);
  assert.equal(h.requests.length, 2);
  assertNoPii(h.root);
  newDispose();
});

test('clearing one root leaves another office selection independent', async () => {
  const mount = await loadMount();
  const first = harness();
  const second = harness();
  const dispose = mount(first);
  mount(second);
  for (const h of [first, second]) { enter(h, REFERENCE_A); submit(h); }
  await setImmediate();
  dispose();
  assert.equal(first.root.innerHTML, '');
  assert.match(second.root.textContent, /Synthetic Applicant Alpha/);
});
