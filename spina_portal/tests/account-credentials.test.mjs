import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { ApiError } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/account-credentials.js', import.meta.url);
const CLIENT = '11111111-1111-4111-8111-111111111111';
const STAFF = '22222222-2222-4222-8222-222222222222';
const RESET = `/api/v1/management/accounts/${CLIENT}/password/reset`;
const client = { id: CLIENT, username: 'test.client', full_name: 'Test Client',
  email: 'client@example.invalid', status: 'active', roles: ['client'], device_count: 1,
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' };
const staff = { ...client, id: STAFF, username: 'test.staff', full_name: 'Test Staff', roles: ['employee'] };

async function load() {
  assert.equal(existsSync(moduleUrl), true, 'Shared credential controls must exist');
  return import(moduleUrl.href);
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function response(account = client) {
  return { account: { ...account }, credentials: { username: account.username, password: 'OneTime<Test>&07' },
    delivery: { sent: false, detail: 'Provide the displayed password directly.' }, audit_recorded: true };
}

async function harness({ roles = ['employee'], permissions = ['client.credential.manage'], session } = {}) {
  const { mountAccountCredentials } = await load();
  const h = { root: new Element(), controller: new AbortController(), requests: [], online: true,
    accounts: [client], resetResult: response(), session: session ?? { user: { roles }, permissions } };
  h.api = { async request(path, options = {}) {
    h.requests.push({ path, options });
    if (options.method === 'PATCH') {
      if (h.ownError) throw h.ownError;
      return h.ownPending?.promise ?? { success: true };
    }
    if (options.method === 'POST') {
      if (h.resetError) throw h.resetError;
      return h.resetPending?.promise ?? h.resetResult;
    }
    if (h.searchError) throw h.searchError;
    return h.searchPending?.promise ?? { accounts: h.accounts };
  } };
  h.dispose = mountAccountCredentials({ root: h.root, api: h.api, session: h.session,
    signal: h.controller.signal, isOnline: () => h.online });
  return h;
}

function button(root, label) {
  const found = root.querySelectorAll('button').find((item) => item.textContent === label);
  assert.ok(found, `Missing ${label} button`);
  return found;
}

function own(h, password = ' New exact password! ', confirmation = password) {
  h.root.querySelector('[name="newPassword"]').value = password;
  h.root.querySelector('[name="confirmPassword"]').value = confirmation;
  fire(h.root.querySelector('[data-credential-own-form]'), 'submit');
}

async function search(h, query = 'Test Client') {
  const input = h.root.querySelector('[name="accountQuery"]');
  input.value = query;
  fire(input, 'input');
  fire(h.root.querySelector('[data-credential-search-form]'), 'submit');
  await setImmediate();
}

async function select(h) {
  await search(h);
  fire(button(h.root, 'Select account'), 'click');
}

function confirmReset(h) { fire(h.root.querySelector('[data-credential-reset-form]'), 'submit'); }

for (const roles of [[], ['owner'], ['client'], ['management', 'client'], ['employee', 'client']]) {
  test(`credential controls deny unknown or Client membership: ${roles.join(',') || 'none'}`, async (t) => {
    const h = await harness({ roles, permissions: ['account.manage', 'client.credential.manage'] });
    t.after(h.dispose);
    assert.equal(h.root.querySelector('form'), null);
    assert.deepEqual(h.requests, []);
  });
}

test('Client membership also wins across legacy role fields', async (t) => {
  const h = await harness({ session: { role: 'client', user: { roles: ['management'] }, permissions: ['account.manage'] } });
  t.after(h.dispose);
  assert.equal(h.root.querySelector('form'), null);
});

for (const fixture of [
  { roles: ['collector'], permissions: ['client.credential.manage'], reset: false },
  { roles: ['employee'], permissions: ['account.manage'], reset: false },
  { roles: ['employee'], permissions: ['client.credential.manage.extra'], reset: false },
  { roles: ['employee'], permissions: ['client.credential.manage'], reset: true },
  { roles: ['management'], permissions: ['account.manage'], reset: true },
]) {
  test(`${fixture.roles[0]} reset access requires matching server permission: ${fixture.permissions[0]}`, async (t) => {
    const h = await harness(fixture);
    t.after(h.dispose);
    assert.ok(h.root.querySelector('[data-credential-own-form]'));
    assert.equal(Boolean(h.root.querySelector('[data-credential-search-form]')), fixture.reset);
  });
}

test('staff self-change preserves exact password and sends one PATCH despite duplicate submission', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  h.ownPending = deferred();
  own(h);
  own(h);
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].path, '/api/v1/auth/password');
  assert.equal(h.requests[0].options.method, 'PATCH');
  assert.deepEqual(h.requests[0].options.body, { password: ' New exact password! ' });
  assert.equal(h.root.querySelector('[name="newPassword"]').value, '');
  h.ownPending.resolve({ success: true });
  await setImmediate();
  assert.match(h.root.textContent, /Password changed/);
  assert.equal(h.root.querySelector('[name="confirmPassword"]').value, '');
});

for (const [password, confirmation] of [['', ''], ['a'.repeat(201), 'a'.repeat(201)], ['Valid input', 'different']]) {
  test(`invalid self-change sends no request: ${password.length}/${confirmation.length}`, async (t) => {
    const h = await harness();
    t.after(h.dispose);
    own(h, password, confirmation);
    assert.equal(h.requests.length, 0);
    assert.match(h.root.textContent, /password|match/i);
  });
}

test('cancel clears both new-password inputs without a request', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  const input = h.root.querySelector('[name="newPassword"]');
  const confirm = h.root.querySelector('[name="confirmPassword"]');
  input.value = confirm.value = 'Do not keep this';
  fire(button(h.root, 'Clear password'), 'click');
  assert.equal(input.value, '');
  assert.equal(confirm.value, '');
  assert.equal(h.requests.length, 0);
});

test('offline blocks self-change and search using the connection state at submission', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  h.online = false;
  own(h);
  await search(h);
  assert.equal(h.requests.length, 0);
  assert.match(h.root.textContent, /online|connection/i);
});

test('Employee searches only Clients, shows returned identity, and requires confirmation before reset', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  h.accounts = [staff, client];
  await select(h);
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].path, '/api/v1/management/client-accounts?q=Test%20Client');
  assert.doesNotMatch(h.root.textContent, /Test Staff/);
  const confirmation = h.root.querySelector('[data-credential-selection]');
  assert.match(confirmation.textContent, /test.client/);
  assert.match(confirmation.textContent, /Test Client/);
  assert.match(confirmation.textContent, /client@example.invalid/);
  assert.match(confirmation.textContent, /previous password|old password/i);
  fire(button(h.root, 'Cancel reset'), 'click');
  assert.equal(h.root.querySelector('[data-credential-reset-form]'), null);
  assert.equal(h.requests.length, 1);
});

test('Management with account.manage can select and reset a returned staff account', async (t) => {
  const h = await harness({ roles: ['management'], permissions: ['account.manage'] });
  t.after(h.dispose);
  h.accounts = [staff];
  h.resetResult = response(staff);
  await select(h);
  assert.equal(h.requests[0].path, '/api/v1/management/accounts?q=Test%20Client&limit=25');
  confirmReset(h);
  await setImmediate();
  assert.equal(h.requests[1].path, `/api/v1/management/accounts/${STAFF}/password/reset`);
  assert.equal(h.requests[1].options.method, 'POST');
  assert.equal(h.requests[1].options.body, undefined);
  assert.match(h.root.textContent, /test.staff/);
});

test('reset success is escaped, one-time, and duplicate clicks never create another password', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  await select(h);
  h.resetPending = deferred();
  const form = h.root.querySelector('[data-credential-reset-form]');
  fire(form, 'submit');
  fire(form, 'submit');
  assert.equal(h.requests.filter((r) => r.options.method === 'POST').length, 1);
  assert.equal(h.requests[1].path, RESET);
  h.resetPending.resolve(response());
  await setImmediate();
  const result = h.root.querySelector('[data-credential-result]');
  assert.match(result.innerHTML, /OneTime&lt;Test&gt;&amp;07/);
  assert.match(result.textContent, /once|one-time/i);
  assert.match(result.textContent, /Not sent/);
  assert.equal(result.querySelector('Test'), null);
  const issued = result.querySelector('[data-credential-issued-password]');
  assert.equal(issued.getAttribute('type'), 'password');
  fire(button(h.root, 'Show password'), 'click');
  assert.equal(issued.getAttribute('type'), 'text');
  fire(button(h.root, 'Dismiss credentials'), 'click');
  assert.equal(issued.value, '');
  assert.equal(issued.getAttribute('value'), null);
  assert.equal(result.innerHTML, '');
  fire(form, 'submit');
  assert.equal(h.requests.filter((r) => r.options.method === 'POST').length, 1);
});

test('offline reset is refused after an online search and selection', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  await select(h);
  h.online = false;
  confirmReset(h);
  await setImmediate();
  assert.equal(h.requests.length, 1);
  assert.match(h.root.textContent, /online|connection/i);
});

test('changing search input invalidates detached result buttons and reset confirmation', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  await select(h);
  const selectButton = button(h.root, 'Select account');
  const form = h.root.querySelector('[data-credential-reset-form]');
  const input = h.root.querySelector('[name="accountQuery"]');
  input.value = 'Different';
  fire(input, 'input');
  fire(selectButton, 'click');
  fire(form, 'submit');
  await setImmediate();
  assert.equal(h.requests.length, 1);
  assert.equal(h.root.querySelector('[data-credential-reset-form]'), null);
});

test('a superseded search cannot restore previous accounts or select them', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  const pending = deferred();
  h.searchPending = pending;
  await search(h, 'Old');
  h.searchPending = null;
  h.accounts = [{ ...client, username: 'current.client', full_name: 'Current Client' }];
  await search(h, 'Current');
  pending.resolve({ accounts: [client] });
  await setImmediate();
  assert.match(h.root.textContent, /Current Client/);
  assert.doesNotMatch(h.root.textContent, /Test Client/);
});

for (const failure of ['network', 'mismatched-account', 'missing-password', 'invalid-delivery']) {
  test(`uncertain reset result is not exposed or repeated: ${failure}`, async (t) => {
    const h = await harness();
    t.after(h.dispose);
    await select(h);
    if (failure === 'network') h.resetError = new ApiError('secret must not be shown', { code: 'network_uncertain' });
    if (failure === 'mismatched-account') h.resetResult.account.id = STAFF;
    if (failure === 'missing-password') h.resetResult.credentials.password = '';
    if (failure === 'invalid-delivery') h.resetResult.delivery.sent = 'yes';
    const form = h.root.querySelector('[data-credential-reset-form]');
    fire(form, 'submit');
    await setImmediate();
    fire(form, 'submit');
    await search(h);
    assert.equal(h.requests.filter((r) => r.options.method === 'POST').length, 1);
    assert.doesNotMatch(h.root.textContent, /OneTime|secret must not be shown/);
    assert.match(h.root.textContent, /could not confirm|unconfirmed/i);
    assert.match(h.root.textContent, /do not repeat|before.*again/i);
  });
}

test('an audit failure after a successful reset still shows the returned credential once', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  h.resetResult.audit_recorded = false;
  await select(h);
  confirmReset(h);
  await setImmediate();
  assert.match(h.root.innerHTML, /OneTime&lt;Test&gt;&amp;07/);
  assert.match(h.root.textContent, /audit/i);
  assert.match(h.root.textContent, /changed|replaced/i);
  assert.equal(h.requests.filter((r) => r.options.method === 'POST').length, 1);
});

test('an unconfirmed self-change clears inputs and prevents another mutation', async (t) => {
  const h = await harness();
  t.after(h.dispose);
  h.ownError = new ApiError('sensitive detail', { code: 'network_uncertain' });
  own(h);
  await setImmediate();
  own(h);
  assert.equal(h.requests.length, 1);
  assert.equal(h.root.querySelector('[name="newPassword"]').value, '');
  assert.match(h.root.textContent, /could not confirm|unconfirmed/i);
  assert.doesNotMatch(h.root.textContent, /sensitive detail/);
});

for (const status of [401, 403]) {
  test(`access denial ${status} clears account details and makes controls inert`, async (t) => {
    const h = await harness();
    t.after(h.dispose);
    await select(h);
    const ownForm = h.root.querySelector('[data-credential-own-form]');
    const query = h.root.querySelector('[name="accountQuery"]');
    h.resetError = new ApiError('private error details', { status });
    confirmReset(h);
    await setImmediate();
    fire(ownForm, 'submit');
    assert.equal(h.requests.length, 2);
    assert.equal(query.value, '');
    assert.doesNotMatch(h.root.textContent, /Test Client|test.client|private error/);
    assert.match(h.root.textContent, /access.*no longer|sign in again/i);
  });
}

for (const mode of ['cleanup', 'abort']) {
  test(`${mode} clears inputs and displayed credentials and makes detached forms inert`, async (t) => {
    const h = await harness();
    t.after(h.dispose);
    await select(h);
    confirmReset(h);
    await setImmediate();
    const result = h.root.querySelector('[data-credential-result]');
    const form = h.root.querySelector('[data-credential-own-form]');
    const input = h.root.querySelector('[name="newPassword"]');
    input.value = 'private typed value';
    if (mode === 'abort') h.controller.abort();
    else h.dispose();
    assert.equal(input.value, '');
    assert.equal(result.innerHTML, '');
    assert.equal(h.root.innerHTML, '');
    fire(form, 'submit');
    assert.equal(h.requests.length, 2);
    assert.equal(h.requests[1].options.signal.aborted, true);
  });

  test(`${mode} ignores a late successful reset containing a password`, async (t) => {
    const h = await harness();
    t.after(h.dispose);
    await select(h);
    h.resetPending = deferred();
    confirmReset(h);
    if (mode === 'abort') h.controller.abort();
    else h.dispose();
    h.resetPending.resolve(response());
    await setImmediate();
    assert.equal(h.root.innerHTML, '');
  });
}

test('aborted mount produces no controls or requests', async () => {
  const { mountAccountCredentials } = await load();
  const controller = new AbortController();
  controller.abort();
  const root = new Element();
  mountAccountCredentials({ root, api: { request() { assert.fail('No request expected'); } },
    session: { user: { roles: ['employee'] } }, signal: controller.signal });
  assert.equal(root.innerHTML, '');
});

test('an absent Account mount is a no-op with a callable cleanup', async () => {
  const { mountAccountCredentials } = await load();
  const cleanup = mountAccountCredentials({ root: null, session: { user: { roles: ['employee'] } },
    api: { request() { assert.fail('No request expected'); } } });
  assert.equal(typeof cleanup, 'function');
  cleanup();
});
