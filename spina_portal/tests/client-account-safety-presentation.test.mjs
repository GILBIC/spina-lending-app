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

function mount({ api }) {
  const root = new Element();
  root.innerHTML = clientAccountAdminMarkup();
  hydrateDataset(root);
  bindClientAccountAdmin({ root, api });
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

test('Management empty Renewal and Support queues use compact status rows', () => {
  assert.match(
    managementSource,
    /data-management-queue-empty="renewals"/,
  );
  assert.match(
    managementSource,
    /data-management-queue-empty="support"/,
  );
  assert.match(managementSource, /No renewal requests waiting/i);
  assert.match(managementSource, /No open support requests/i);
  assert.doesNotMatch(
    managementSource,
    /emptyState\('No pending renewal request requires review\.'\)/,
  );
  assert.doesNotMatch(
    managementSource,
    /emptyState\('No open support request requires review\.'\)/,
  );
});
