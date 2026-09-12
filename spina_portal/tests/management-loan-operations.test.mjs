import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);
const serviceWorkerSource = await readFile(
  new URL('../sw.js', import.meta.url),
  'utf8',
);

async function importOperationsModule() {
  try {
    return await import('../assets/management-loan-operations.js');
  } catch {
    return {};
  }
}

test('Management Loan Operations stays Management-only without inventing a Web permission', () => {
  const management = availableRoleActions('management', []);
  const employee = availableRoleActions('employee', []);
  const collector = availableRoleActions('collector', []);

  const action = management.find((entry) => entry.key === 'management-loan-operations');

  assert.ok(action);
  assert.equal(action.path, '/api/v1/management/loan-operations');
  assert.equal(action.section, 'Operations');
  assert.equal(Object.hasOwn(action, 'permission'), false);
  assert.equal(
    employee.some((entry) => entry.path === '/api/v1/management/loan-operations'),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path === '/api/v1/management/loan-operations'),
    false,
  );
});

test('Loan Operations loader uses only the existing protected monitoring endpoint', async () => {
  const operations = await importOperationsModule();
  assert.equal(typeof operations.loadManagementLoanOperations, 'function');

  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      return { summary: {}, entries: [], audits: [], notice: 'Read only.' };
    },
  };

  const result = await operations.loadManagementLoanOperations(api, {
    query: ' Ana / 001 ',
    status: 'submitted',
  });

  assert.equal(result.notice, 'Read only.');
  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/loan-operations?q=Ana%20%2F%20001&status=submitted',
      options: {},
    },
  ]);
});

test('Loan Operations markup displays server values without recomputing financial totals', async () => {
  const operations = await importOperationsModule();
  assert.equal(typeof operations.managementLoanOperationsMarkup, 'function');

  const markup = operations.managementLoanOperationsMarkup({
    summary: {
      latest_collection_date: '2026-09-12',
      latest_day_amount: '8888.00',
      latest_day_payment_count: 12,
      latest_day_unable_to_pay_count: 3,
      unremitted_amount: '9999.00',
      unremitted_entry_count: 7,
      pending_remittance_amount: '5555.00',
      pending_remittance_count: 4,
      received_remittance_amount: '4444.00',
      received_remittance_count: 5,
      correction_count: 2,
      void_count: 1,
    },
    entries: [
      {
        transaction_id: 'tx-1',
        receipt_number: 'OR-1001',
        collection_date: '2026-09-12',
        accepted_at: '2026-09-12T08:30:00+08:00',
        client_code: 'C-001',
        client_name: 'Ana <Client>',
        loan_number: 'LN-001',
        loan_type_name: 'Regular',
        collector_name: 'Collector & One',
        entry_type: 'payment',
        amount: '123.45',
        official_balance: '3210.50',
        covered_dates: ['2026-09-10', '2026-09-11'],
        edit_version: 2,
        status: 'submitted',
        remittance_number: 'REM-77',
        void_reason: null,
      },
    ],
    audits: [
      {
        event_id: 'audit-1',
        event_type: 'correction',
        happened_at: '2026-09-12T09:00:00+08:00',
        transaction_id: 'tx-1',
        receipt_number: 'OR-1001',
        client_name: 'Ana <Client>',
        loan_number: 'LN-001',
        actor_name: 'Manager & One',
        reason: 'Corrected <reason>',
      },
    ],
    notice: 'Server-controlled read-only monitoring notice.',
  });

  assert.match(markup, /8,888\.00/);
  assert.match(markup, /9,999\.00/);
  assert.match(markup, /5,555\.00/);
  assert.match(markup, /4,444\.00/);
  assert.match(markup, /123\.45/);
  assert.match(markup, /3,210\.50/);
  assert.match(markup, /OR-1001/);
  assert.match(markup, /REM-77/);
  assert.match(markup, /Ana &lt;Client&gt;/);
  assert.match(markup, /Collector &amp; One/);
  assert.match(markup, /Corrected &lt;reason&gt;/);
  assert.match(markup, /Manager &amp; One/);
  assert.match(markup, /Server-controlled read-only monitoring notice\./);
  assert.doesNotMatch(markup, />123\.45<.*>9,999\.00</s);
});

test('Loan Operations binding reloads only its results with the selected server filters', async () => {
  const operations = await importOperationsModule();
  assert.equal(typeof operations.bindManagementLoanOperations, 'function');

  const formListeners = {};
  const statusListeners = {};
  const queryInput = { value: ' Ana ' };
  const statusInput = {
    value: 'received',
    addEventListener(type, handler) {
      statusListeners[type] = handler;
    },
  };
  const form = {
    addEventListener(type, handler) {
      formListeners[type] = handler;
    },
    querySelector(selector) {
      if (selector === '[name="q"]') return queryInput;
      if (selector === '[name="status"]') return statusInput;
      return null;
    },
  };
  const target = { innerHTML: '' };
  const root = {
    querySelector(selector) {
      if (selector === '#management-loan-operations-search') return form;
      if (selector === '#management-loan-operations-results') return target;
      return null;
    },
  };
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      return {
        summary: {},
        entries: [],
        audits: [],
        notice: 'Filtered operations from server.',
      };
    },
  };

  operations.bindManagementLoanOperations({ root, api });

  assert.equal(typeof formListeners.submit, 'function');
  assert.equal(typeof statusListeners.change, 'function');
  await formListeners.submit({ preventDefault() {} });

  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/loan-operations?q=Ana&status=received',
      options: {},
    },
  ]);
  assert.match(target.innerHTML, /Filtered operations from server\./);

  queryInput.value = 'OR-1001';
  statusInput.value = 'voided';
  await statusListeners.change();
  assert.equal(
    calls[1].path,
    '/api/v1/management/loan-operations?q=OR-1001&status=voided',
  );
});

test('Management workspace mounts the isolated Loan Operations read-only surface', () => {
  assert.match(managementSource, /management-loan-operations\.js/);
  assert.match(managementSource, /loadManagementLoanOperations/);
  assert.match(managementSource, /managementLoanOperationsMarkup/);
  assert.match(managementSource, /bindManagementLoanOperations/);
  assert.match(managementSource, /id="management-loan-operations"/);
  assert.match(managementSource, /management-loan-operations-search/);
  assert.doesNotMatch(managementSource, /hasPermission\(session, ['"]loan-operations/);
});

test('installed Web shell precaches the isolated Management Loan Operations dependency', () => {
  assert.match(serviceWorkerSource, /'\/assets\/management-loan-operations\.js'/);
});
