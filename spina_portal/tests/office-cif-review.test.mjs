import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import test from 'node:test';

import { SpinaApi } from '../assets/api.js';
import { MemoryStorage, SessionStore } from '../assets/session.js';

const moduleUrl = new URL('../assets/office-cif-review.js', import.meta.url);
const CLIENT_A = '11111111-1111-4111-8111-111111111111';
const CLIENT_B = '22222222-2222-4222-8222-222222222222';
const CIF_A = '33333333-3333-4333-8333-333333333333';
const CIF_B = '66666666-6666-4666-8666-666666666666';
const PERMISSION = 'client_onboarding.requirement.review';
const OLD_PII = 'Previous Applicant Private Address';

async function loadMount() {
  assert.equal(
    existsSync(moduleUrl),
    true,
    'Office CIF review panel is not implemented',
  );
  const { mountOfficeCifReview } = await import(moduleUrl.href);
  assert.equal(typeof mountOfficeCifReview, 'function');
  return mountOfficeCifReview;
}

function review(overrides = {}) {
  return {
    client_id: CLIENT_A,
    cif_version_id: CIF_A,
    version_number: 7,
    status: 'draft',
    liveness_status: 'pending',
    full_name: 'Synthetic Applicant Alpha',
    phone_number: '09170000001',
    email: 'alpha@example.test',
    present_address: '17 Synthetic Test Street',
    review_scope: 'cif_information_only',
    ...overrides,
  };
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function harness({ role = 'employee', permissions = [PERMISSION], fetchImpl } = {}) {
  const sessionStorage = new MemoryStorage();
  const localStorage = new MemoryStorage();
  const store = new SessionStore({
    sessionStorageRef: sessionStorage,
    localStorageRef: localStorage,
    cryptoRef: { randomUUID: () => '44444444-4444-4444-8444-444444444444' },
  });
  const session = store.save({
    access_token: 'synthetic-access-token',
    refresh_token: 'synthetic-refresh-token',
    user: {
      id: '55555555-5555-4555-8555-555555555555',
      role,
      roles: [role],
      permissions,
    },
    permissions,
  });
  store.deviceId();
  const storageMutations = [];
  for (const storage of [sessionStorage, localStorage]) {
    for (const method of ['setItem', 'removeItem', 'clear']) {
      const original = storage[method].bind(storage);
      storage[method] = (...args) => {
        storageMutations.push({ method, args });
        return original(...args);
      };
    }
  }
  const requests = [];
  const api = new SpinaApi({
    apiBaseUrl: 'https://api.example.test',
    sessionStore: store,
    fetchImpl: (url, init) => {
      requests.push({ url, init });
      return fetchImpl ? fetchImpl(url, init) : Promise.resolve(jsonResponse(review()));
    },
  });
  return { api, session, requests, sessionStorage, storageMutations };
}

function textContent(root) {
  return root.innerHTML.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function assertNoOldPii(root) {
  assert.doesNotMatch(root.innerHTML, /Previous Applicant Private Address/);
}

for (const role of ['employee', 'management']) {
  test(`${role} reviews only the selected CIF through one authenticated GET`, async () => {
    const mount = await loadMount();
    const h = harness({ role });
    const root = { innerHTML: OLD_PII };
    const savedSession = h.sessionStorage.getItem(SessionStore.SESSION_KEY);

    await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

    assert.equal(h.requests.length, 1);
    assert.equal(
      h.requests[0].url,
      'https://api.example.test/api/v1/management/clients/11111111-1111-4111-8111-111111111111/cif/review-summary',
    );
    assert.equal(h.requests[0].init.method, 'GET');
    assert.equal(h.requests[0].init.body, undefined);
    assert.equal(h.requests[0].init.headers.Authorization, 'Bearer synthetic-access-token');
    assert.equal(
      h.requests[0].init.headers['X-Device-Id'],
      'spina-web-44444444-4444-4444-8444-444444444444',
    );
    const rendered = textContent(root);
    for (const value of [
      'Synthetic Applicant Alpha', '09170000001',
      'alpha@example.test', '17 Synthetic Test Street',
    ]) assert.ok(rendered.includes(value));
    assert.match(rendered, /(?:CIF\s+)?version\s*7/i);
    assert.match(rendered, /information\s+review|review.*information/i);
    assert.doesNotMatch(root.innerHTML, /<(?:form|input|textarea|select)\b/i);
    assert.doesNotMatch(root.innerHTML, /<button\b[^>]*>[\s\S]*?(?:confirm|approve|sign|release|activate)/i);
    assertNoOldPii(root);
    assert.equal(h.sessionStorage.getItem(SessionStore.SESSION_KEY), savedSession);
    assert.deepEqual(h.storageMutations, []);
  });
}

for (const [role, permissions] of [
  ['collector', [PERMISSION]],
  ['client', [PERMISSION]],
  ['employee', ['client_onboarding.requirement.review.extra']],
]) {
  test(`${role} without the exact office authority clears PII before any request`, async () => {
    const mount = await loadMount();
    const h = harness({ role, permissions });
    const root = { innerHTML: OLD_PII };

    await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

    assert.equal(h.requests.length, 0);
    assertNoOldPii(root);
    assert.match(textContent(root), /permission|not available|not permitted|office|access/i);
  });
}

for (const clientId of [null, '../other-client?include=private']) {
  test(`${clientId === null ? 'No' : 'Invalid'} selected Client clears PII without a request`, async () => {
    const mount = await loadMount();
    const h = harness();
    const root = { innerHTML: OLD_PII };

    await mount({ root, api: h.api, session: h.session, clientId });

    assert.equal(h.requests.length, 0);
    assertNoOldPii(root);
    assert.match(textContent(root), /select|choose|invalid|valid|unavailable/i);
  });
}

test('a null optional email keeps the remaining CIF information reviewable', async () => {
  const mount = await loadMount();
  const h = harness({ fetchImpl: async () => jsonResponse(review({ email: null })) });
  const root = { innerHTML: '' };

  await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

  assert.match(textContent(root), /Synthetic Applicant Alpha/);
  assert.match(textContent(root), /17 Synthetic Test Street/);
  assert.match(textContent(root), /email/i);
  assert.doesNotMatch(textContent(root), /\bnull\b|\bundefined\b/i);
});

test('server-provided name address and email render as text rather than executable markup', async () => {
  const mount = await loadMount();
  const h = harness({
    fetchImpl: async () => jsonResponse(review({
      full_name: '<img src=x onerror=alert(1)> Applicant & Co',
      present_address: '<script>alert(2)</script> Test Street',
      email: '<svg onload=alert(3)>@example.test',
    })),
  });
  const root = { innerHTML: '' };

  await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

  assert.doesNotMatch(root.innerHTML, /<(?:img|script|svg)\b/i);
  assert.match(root.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt; Applicant &amp; Co/);
  assert.match(root.innerHTML, /&lt;script&gt;alert\(2\)&lt;\/script&gt; Test Street/);
  assert.match(root.innerHTML, /&lt;svg onload=alert\(3\)&gt;@example\.test/);
});

test('unexpected evidence and readiness fields never become review content or status claims', async () => {
  const mount = await loadMount();
  const h = harness({
    fetchImpl: async () => jsonResponse(review({
      applicant_confirmation_evidence_reference: 'private-evidence-sentinel',
      baseline_face_scan_evidence_reference: 'private-biometric-sentinel',
      approval_status: 'loan-approved-sentinel',
      review_confirmation_status: 'confirmed-sentinel',
      privacy_status: 'privacy-complete-sentinel',
      password: 'private-credential-sentinel',
    })),
  });
  const root = { innerHTML: '' };

  await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

  assert.match(textContent(root), /Synthetic Applicant Alpha/);
  assert.doesNotMatch(root.innerHTML, /sentinel|review_confirmation_status|approval_status|privacy_status/);
});

for (const [reason, overrides] of [
  ['a different Client', { client_id: CLIENT_B }],
  ['a different review scope', { review_scope: 'loan_application_information_only' }],
  ['missing CIF identity', { cif_version_id: null }],
  ['an invalid CIF version', { version_number: 0 }],
  ['an absent required information field', { full_name: undefined }],
  ['non-text contact information', { phone_number: 9170000001 }],
  ['non-text address information', { present_address: null }],
  ['an absent nullable email field', { email: undefined }],
]) {
  test(`a response with ${reason} cannot display applicant information`, async () => {
    const mount = await loadMount();
    const h = harness({ fetchImpl: async () => jsonResponse(review(overrides)) });
    const root = { innerHTML: OLD_PII };

    await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

    assertNoOldPii(root);
    assert.doesNotMatch(root.innerHTML, /Synthetic Applicant Alpha|17 Synthetic Test Street|alpha@example\.test/);
    assert.match(textContent(root), /unavailable|invalid|could not|cannot|does not match|unable/i);
  });
}

for (const [reason, fetchImpl] of [
  ['server denial', async () => jsonResponse({ detail: 'Office access denied. <img src=x onerror=alert(4)> error-sentinel' }, 403)],
  ['connection failure', async () => { throw new TypeError('Synthetic network failure'); }],
]) {
  test(`${reason} replaces previous applicant data with an error`, async () => {
    const mount = await loadMount();
    const h = harness({ fetchImpl });
    const root = { innerHTML: OLD_PII };

    await mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

    assertNoOldPii(root);
    assert.doesNotMatch(root.innerHTML, /Synthetic Applicant Alpha/);
    assert.doesNotMatch(root.innerHTML, /<(?:img|script|svg)\b/i);
    assert.match(textContent(root), /denied|unavailable|could not|cannot|connection|unable/i);
  });
}

test('selecting another Client removes the previous PII immediately while loading', async () => {
  const mount = await loadMount();
  const pending = deferred();
  const h = harness({ fetchImpl: () => pending.promise });
  const root = { innerHTML: OLD_PII };

  const mounted = mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

  assertNoOldPii(root);
  assert.match(textContent(root), /loading/i);
  pending.resolve(jsonResponse(review()));
  await mounted;
  assert.match(textContent(root), /Synthetic Applicant Alpha/);
});

for (const outcome of ['success', 'failure']) {
  test(`an older request ${outcome} cannot replace the newer Client review`, async () => {
    const mount = await loadMount();
    const pending = deferred();
    const h = harness({
      fetchImpl: (url) => url.includes(CLIENT_A)
        ? pending.promise
        : Promise.resolve(jsonResponse(review({ client_id: CLIENT_B, cif_version_id: CIF_B, full_name: 'Synthetic Applicant Beta' }))),
    });
    const root = { innerHTML: '' };
    const first = mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });
    await mount({ root, api: h.api, session: h.session, clientId: CLIENT_B });
    assert.match(textContent(root), /Synthetic Applicant Beta/);
    const newerReview = root.innerHTML;

    if (outcome === 'success') pending.resolve(jsonResponse(review()));
    else pending.reject(new TypeError('Old synthetic network failure'));
    await first;

    assert.equal(root.innerHTML, newerReview);
    assert.equal(h.requests.length, 2);
  });
}

for (const reason of ['selection cleared', 'office authority removed']) {
  test(`pending data stays hidden after ${reason}`, async () => {
    const mount = await loadMount();
    const pending = deferred();
    const h = harness({ fetchImpl: () => pending.promise });
    const root = { innerHTML: '' };
    const first = mount({ root, api: h.api, session: h.session, clientId: CLIENT_A });

    await mount({
      root,
      api: h.api,
      session: reason === 'selection cleared' ? h.session : null,
      clientId: reason === 'selection cleared' ? null : CLIENT_A,
    });
    const clearedReview = root.innerHTML;
    pending.resolve(jsonResponse(review()));
    await first;

    assert.equal(h.requests.length, 1);
    assert.equal(root.innerHTML, clearedReview);
    assert.doesNotMatch(root.innerHTML, /Synthetic Applicant Alpha|17 Synthetic Test Street/);
  });
}

test('independent review roots do not invalidate each other', async () => {
  const mount = await loadMount();
  const pending = deferred();
  const h = harness({
    fetchImpl: (url) => url.includes(CLIENT_A)
      ? pending.promise
      : Promise.resolve(jsonResponse(review({ client_id: CLIENT_B, cif_version_id: CIF_B, full_name: 'Synthetic Applicant Beta' }))),
  });
  const firstRoot = { innerHTML: '' };
  const secondRoot = { innerHTML: '' };
  const first = mount({ root: firstRoot, api: h.api, session: h.session, clientId: CLIENT_A });
  await mount({ root: secondRoot, api: h.api, session: h.session, clientId: CLIENT_B });
  pending.resolve(jsonResponse(review()));
  await first;

  assert.match(textContent(firstRoot), /Synthetic Applicant Alpha/);
  assert.match(textContent(secondRoot), /Synthetic Applicant Beta/);
  assert.equal(h.requests.length, 2);
});
