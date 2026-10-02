import {mountManagementWorkspace} from '../assets/roles/management.js';
import {mountRoleTask, activateManagementTask} from './helpers/management-task-harness.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import {
  bindClientAccountAdmin,
  clientAccountAdminMarkup,
} from '../assets/client-account-admin.js';
import { Element, fire } from './helpers/dom.mjs';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);

const CLIENT_A = '11111111-1111-4111-8111-111111111111';
const CLIENT_B = '22222222-2222-4222-8222-222222222222';

const clientA = {
  id: CLIENT_A,
  full_name: 'Maria A',
  client_code: 'A-001',
  area: 'Cardona',
  phone_number: '09170000001',
  status: 'active',
};
const clientB = {
  id: CLIENT_B,
  full_name: 'Maria B',
  client_code: 'B-001',
  area: 'Morong',
  phone_number: '09170000002',
  status: 'active',
};

const tick = async () => {
  await setImmediate();
  await setImmediate();
};

class FixtureFormData {
  constructor(form) {
    this.form = form;
  }

  get(name) {
    return this.form.querySelector(`[name="${name}"]`)?.value ?? null;
  }
}

function installFormData(t) {
  const original = globalThis.FormData;
  globalThis.FormData = FixtureFormData;
  t.after(() => {
    globalThis.FormData = original;
  });
}

function hydrateDataset(root) {
  for (const element of root.querySelectorAll('[data-client-id]')) {
    element.dataset = {
      clientId: element.getAttribute('data-client-id'),
    };
  }
  for (const element of root.querySelectorAll('button')) {
    element.dataset ||= {};
  }
}

function mount({ api, session = { user: { roles: ['management'] }, permissions: ['account.manage'] }, signal, isOnline } = {}) {
  const root = new Element();
  root.innerHTML = clientAccountAdminMarkup();
  hydrateDataset(root);
  root.cleanup = bindClientAccountAdmin({ root, api, session, signal, isOnline });
  return root;
}

test('Client-account form is progressive and hidden until a current borrower is selected', () => {
  const root = new Element();
  root.innerHTML = clientAccountAdminMarkup();

  assert.ok(root.querySelector('#management-client-account-search'));
  const stage = root.querySelector('[data-client-account-create-stage]');
  assert.ok(stage);
  assert.equal(stage.getAttribute('hidden'), '');
  assert.doesNotMatch(root.textContent, /No borrower selected/i);
  assert.match(root.textContent, /Search for an active borrower/i);
});

test('new borrower search invalidates prior borrower and email before new results arrive', async (t) => {
  installFormData(t);
  const calls = [];
  let resolveSecond;
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path.includes('q=first')) return { clients: [clientA] };
      if (path.includes('q=second')) {
        return new Promise((resolve) => {
          resolveSecond = resolve;
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    },
  };
  const root = mount({ api });
  const search = root.querySelector('#management-client-account-search');
  const query = search.querySelector('[name="query"]');
  const create = root.querySelector('#management-client-account-create');
  const stage = root.querySelector('[data-client-account-create-stage]');

  query.value = 'first';
  fire(search, 'submit');
  await tick();
  hydrateDataset(root);
  fire(root.querySelector('.select-client-account-borrower'), 'click');

  create.querySelector('[name="email"]').value = 'maria.a@example.com';
  assert.equal(create.querySelector('[name="clientId"]').value, CLIENT_A);
  assert.equal(stage.getAttribute('hidden'), null);
  assert.equal(create.querySelector('button[type="submit"]').disabled, false);

  query.value = 'second';
  fire(search, 'submit');

  assert.equal(create.querySelector('[name="clientId"]').value, '');
  assert.equal(create.querySelector('[name="email"]').value, '');
  assert.equal(create.querySelector('button[type="submit"]').disabled, true);
  assert.equal(stage.getAttribute('hidden'), '');

  resolveSecond({ clients: [clientB] });
  await tick();
  hydrateDataset(root);
  fire(root.querySelector('.select-client-account-borrower'), 'click');

  assert.equal(create.querySelector('[name="clientId"]').value, CLIENT_B);
  assert.equal(create.querySelector('[name="email"]').value, '');
  assert.equal(stage.getAttribute('hidden'), null);
});

test('changing borrower clears an email entered for the previous borrower', async (t) => {
  installFormData(t);
  const api = {
    async request(path) {
      if (path.includes('client-link-candidates')) {
        return { clients: [clientA, clientB] };
      }
      throw new Error(`Unexpected request: ${path}`);
    },
  };
  const root = mount({ api });
  const search = root.querySelector('#management-client-account-search');
  search.querySelector('[name="query"]').value = 'maria';
  fire(search, 'submit');
  await tick();
  hydrateDataset(root);

  const candidates = root.querySelectorAll('.select-client-account-borrower');
  fire(candidates[0], 'click');
  const create = root.querySelector('#management-client-account-create');
  create.querySelector('[name="email"]').value = 'first@example.com';

  fire(candidates[1], 'click');

  assert.equal(create.querySelector('[name="clientId"]').value, CLIENT_B);
  assert.equal(create.querySelector('[name="email"]').value, '');
});

test('uncertain Client-account creation locks repeat mutation until an authoritative search succeeds', async (t) => {
  installFormData(t);
  const originalConfirm = globalThis.confirm;
  globalThis.confirm = () => true;
  t.after(() => {
    globalThis.confirm = originalConfirm;
  });

  let postCount = 0;
  let searchCount = 0;
  const api = {
    async request(path, options = {}) {
      if (path.includes('client-link-candidates')) {
        searchCount += 1;
        return { clients: [clientA] };
      }
      if (path === '/api/v1/management/client-accounts' && options.method === 'POST') {
        postCount += 1;
        const error = new Error(
          'The connection ended before SPINA could confirm the result.',
        );
        error.code = 'network_uncertain';
        error.status = 0;
        throw error;
      }
      throw new Error(`Unexpected request: ${path}`);
    },
  };

  const root = mount({ api });
  const search = root.querySelector('#management-client-account-search');
  search.querySelector('[name="query"]').value = 'maria';
  fire(search, 'submit');
  await tick();
  hydrateDataset(root);
  fire(root.querySelector('.select-client-account-borrower'), 'click');

  const create = root.querySelector('#management-client-account-create');
  create.querySelector('[name="email"]').value = 'maria@example.com';
  fire(create, 'submit');
  await tick();

  assert.equal(postCount, 1);
  assert.equal(create.querySelector('button[type="submit"]').disabled, true);
  assert.ok(root.querySelector('[data-client-account-uncertain]'));
  assert.match(
    root.querySelector('[data-client-account-uncertain]').textContent,
    /result is uncertain/i,
  );
  assert.match(
    root.querySelector('[data-client-account-uncertain]').textContent,
    /search the borrower again/i,
  );

  fire(create, 'submit');
  await tick();
  assert.equal(postCount, 1, 'uncertain mutation must not be repeated');

  search.querySelector('[name="query"]').value = 'maria';
  fire(search, 'submit');
  await tick();
  hydrateDataset(root);

  assert.equal(searchCount, 2);
  assert.equal(root.querySelector('[data-client-account-uncertain]'), null);
  assert.equal(create.querySelector('[name="clientId"]').value, '');
  assert.equal(create.querySelector('button[type="submit"]').disabled, true);

  fire(root.querySelector('.select-client-account-borrower'), 'click');
  assert.equal(create.querySelector('button[type="submit"]').disabled, false);
});

test('Management empty Renewal and Support queues use actual compact status rows', async (t) => {
  const controller = new AbortController();
  t.after(() => controller.abort());
  const calls = [];
  const root = new Element();
  const context = {root, signal:controller.signal,
    session:{user:{id:CLIENT_A,role:'management'},permissions:['renewal.manage','support.manage']},
    setNavigation(){},api:{async request(path, options){calls.push({path,options});return {requests:[]};}}};
  await mountRoleTask(mountManagementWorkspace, context, 'management-clients-loans', 'management-renewals');
  const renewalRoot = root.querySelector('[data-management-renewal-workflow]');
  const renewalStatus = renewalRoot.querySelector('[data-management-queue-empty="renewals"]');
  assert.ok(renewalStatus, 'the returned empty renewal queue is a compact status row');
  assert.match(renewalStatus.textContent, /No pending renewal requests/);
  assert.equal(renewalStatus.getAttribute('role'), 'status');
  assert.equal(renewalRoot.querySelector('.empty-state'), null);
  await activateManagementTask(context, 'management-operations', 'management-support');
  const supportRoot = root.querySelector('[data-management-support-list]');
  const supportStatus = supportRoot.querySelector('[data-management-queue-empty="support"]');
  assert.ok(supportStatus, 'the returned empty support queue is a compact status row');
  assert.match(supportStatus.textContent, /No open support requests/);
  assert.equal(supportStatus.getAttribute('role'), 'status');
  assert.equal(supportRoot.querySelector('.empty-state'), null);
  assert.equal(renewalRoot.querySelector('[data-management-queue-empty="renewals"]'), renewalStatus);
  assert.ok(calls.some(({path}) => path === '/api/v1/management/renewal-workflow?status=pending'));
  assert.ok(calls.some(({path}) => path === '/api/v1/management/support?status=open&limit=100&offset=0'));
  assert.ok(calls.every(({options}) => !options?.method || options.method === 'GET'));
});

test('editing borrower search makes detached selection controls inert and ignores a superseded response', async (t) => {
  installFormData(t);
  let finishOld;
  const root = mount({ api: { request(path) {
    return path.includes('q=old') ? new Promise((resolve) => { finishOld = resolve; }) : Promise.resolve({ clients: [clientB] });
  } } });
  const form = root.querySelector('#management-client-account-search');
  const query = form.querySelector('[name="query"]');
  query.value = 'old'; fire(form, 'submit');
  query.value = 'new'; fire(query, 'input'); fire(form, 'submit'); await tick();
  hydrateDataset(root);
  const current = root.querySelector('.select-client-account-borrower');
  finishOld({ clients: [clientA] }); await tick();
  assert.doesNotMatch(root.querySelector('#management-client-account-candidates').textContent, /Maria A/);
  query.value = 'different'; fire(query, 'input'); fire(current, 'click');
  assert.equal(root.querySelector('[name="clientId"]').value, '');
  assert.equal(root.querySelector('#management-client-account-create').querySelector('button').disabled, true);
});

test('failed and malformed borrower searches do not unlock uncertain creation', async (t) => {
  installFormData(t);
  const original = globalThis.confirm; globalThis.confirm = () => true; t.after(() => { globalThis.confirm = original; });
  let searches = 0; let posts = 0;
  const root = mount({ api: { async request(path, options = {}) {
    if (options.method === 'POST') { posts += 1; throw Object.assign(new Error('uncertain'), { status: 503 }); }
    searches += 1;
    if (searches === 1) return { clients: [clientA] };
    if (searches === 2) throw new Error('Search unavailable');
    return {};
  } } });
  const search = root.querySelector('#management-client-account-search');
  search.querySelector('[name="query"]').value = 'maria'; fire(search, 'submit'); await tick(); hydrateDataset(root);
  fire(root.querySelector('.select-client-account-borrower'), 'click');
  const create = root.querySelector('#management-client-account-create');
  create.querySelector('[name="email"]').value = 'maria@example.com'; fire(create, 'submit'); await tick();
  for (let index = 0; index < 2; index += 1) {
    fire(search, 'submit'); await tick(); fire(create, 'submit'); await tick();
    assert.ok(root.querySelector('[data-client-account-uncertain]'));
    assert.equal(create.querySelector('button').disabled, true);
  }
  assert.equal(posts, 1);
});

test('pending creation submits once and late credentials cannot survive cleanup', async (t) => {
  installFormData(t);
  const original = globalThis.confirm; globalThis.confirm = () => true; t.after(() => { globalThis.confirm = original; });
  let finish; let posts = 0;
  const root = mount({ api: { async request(path, options = {}) {
    if (options.method === 'POST') { posts += 1; return new Promise((resolve) => { finish = resolve; }); }
    return { clients: [clientA] };
  } } });
  const search = root.querySelector('#management-client-account-search');
  search.querySelector('[name="query"]').value = 'maria'; fire(search, 'submit'); await tick(); hydrateDataset(root);
  fire(root.querySelector('.select-client-account-borrower'), 'click');
  const create = root.querySelector('#management-client-account-create');
  create.querySelector('[name="email"]').value = 'maria@example.com';
  fire(create, 'submit'); fire(create, 'submit'); await tick(); assert.equal(posts, 1);
  root.cleanup();
  finish({ account: { username: 'server.client' }, credentials: { username: 'server.client', password: 'one-time-secret' }, delivery: { sent: false, detail: 'Not sent' } });
  await tick(); fire(create, 'submit'); await tick();
  assert.equal(posts, 1); assert.equal(create.querySelector('[name="email"]').value, '');
  assert.doesNotMatch(root.textContent, /one-time-secret/);
});

for (const session of [
  { user: { roles: ['employee'] }, permissions: ['account.manage'] },
  { user: { roles: ['management'] }, permissions: [] },
]) test('Client creation requires Management membership and account.manage in the active session', async (t) => {
  installFormData(t); let requests = 0;
  const root = mount({ session, api: { async request() { requests += 1; return { clients: [clientA] }; } } });
  const search = root.querySelector('#management-client-account-search');
  search.querySelector('[name="query"]').value = 'maria'; fire(search, 'submit'); await tick();
  assert.equal(requests, 0);
});
