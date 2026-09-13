import assert from 'node:assert/strict';
import test from 'node:test';

import { mountClientWorkspace } from '../assets/roles/client.js';
import { mountCollectorWorkspace } from '../assets/roles/collector.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';

function syntheticRoot() {
  return {
    innerHTML: '',
    dataset: {},
    addEventListener() {},
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
}

function navigationCollector() {
  const items = [];
  return {
    items,
    setNavigation(next) {
      items.push(...next);
    },
  };
}

test('Priority #7 synthetic Client workspace mounts only borrower-owned surfaces', async () => {
  const root = syntheticRoot();
  const navigation = navigationCollector();
  const calls = [];
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') {
        return { profile: { full_name: 'Synthetic Client' }, devices: [] };
      }
      if (path === '/api/v1/client/loans') return { loans: [] };
      if (path === '/api/v1/client/payments') return { payments: [] };
      if (path === '/api/v1/client/statement') {
        return { client: { client_name: 'Synthetic Client' }, loans: [], payments: [] };
      }
      if (path === '/api/v1/client/renewals') return { loans: [], requests: [] };
      if (path === '/api/v1/client/renewal-workflow') return { requests: [] };
      if (path === '/api/v1/client/support') return { requests: [] };
      if (path === '/api/v1/client/gcash/config') return { payment_available: false };
      if (path === '/api/v1/activity-notifications') return [];
      throw new Error(`Unexpected Client request: ${path}`);
    },
  };

  await mountClientWorkspace({ api, root, setNavigation: navigation.setNavigation });

  assert.match(root.innerHTML, /Client workspace/i);
  assert.match(root.innerHTML, /My loans/i);
  assert.match(root.innerHTML, /Statement/i);
  assert.match(root.innerHTML, /Payment instructions/i);
  assert.ok(navigation.items.some((item) => item.label === 'My loans'));
  assert.ok(navigation.items.some((item) => item.label === 'Statement'));
  assert.ok(calls.includes('/api/v1/client/loans'));
  assert.ok(calls.includes('/api/v1/client/statement'));
  assert.equal(calls.some((path) => path.includes('/management/')), false);
  assert.equal(calls.some((path) => path.includes('/collector/')), false);
});

test('Priority #7 synthetic Collector workspace mounts assigned route without Management authority', async () => {
  const root = syntheticRoot();
  const navigation = navigationCollector();
  const calls = [];
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/collector/routes/today') {
        return {
          route_date: '2026-09-14',
          collector_name: 'Synthetic Collector',
          expected_total: '0.00',
          areas: [],
          entries: [],
        };
      }
      if (path === '/api/v1/account') {
        return { profile: { full_name: 'Synthetic Collector' } };
      }
      if (path === '/api/v1/activity-notifications') return [];
      throw new Error(`Unexpected Collector request: ${path}`);
    },
  };

  await mountCollectorWorkspace({
    api,
    root,
    session: { permissions: ['route.view', 'collection.create'] },
    setNavigation: navigation.setNavigation,
  });

  assert.match(root.innerHTML, /Collector workspace/i);
  assert.match(root.innerHTML, /Assigned area ledger/i);
  assert.match(root.innerHTML, /Master Review/i);
  assert.ok(navigation.items.some((item) => item.label === "Today's route"));
  assert.ok(calls.includes('/api/v1/collector/routes/today'));
  assert.equal(calls.some((path) => path.includes('/management/')), false);
});

test('Priority #7 synthetic Employee workspace stays permission-bounded', async () => {
  const root = syntheticRoot();
  const navigation = navigationCollector();
  const calls = [];
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') {
        return { profile: { full_name: 'Synthetic Employee' } };
      }
      if (path === '/api/v1/activity-notifications') return [];
      throw new Error(`Unexpected Employee request: ${path}`);
    },
  };

  await mountEmployeeWorkspace({
    api,
    root,
    session: { permissions: [] },
    setNavigation: navigation.setNavigation,
  });

  assert.match(root.innerHTML, /Employee workspace/i);
  assert.match(root.innerHTML, /Not connected yet/i);
  assert.ok(navigation.items.some((item) => item.label === 'My workday'));
  assert.equal(navigation.items.some((item) => item.label === 'Area Management'), false);
  assert.equal(calls.some((path) => path.includes('/collector/')), false);
  assert.equal(calls.some((path) => path.includes('/management/')), false);
});

test('Priority #7 synthetic Management workspace mounts verified read surfaces', async () => {
  const root = syntheticRoot();
  const navigation = navigationCollector();
  const calls = [];
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') {
        return { profile: { full_name: 'Synthetic Management' } };
      }
      if (path === '/api/v1/management/dashboard-overview') return { metrics: [] };
      if (path === '/api/v1/management/loans?status=active') return { summary: {}, loans: [] };
      if (path === '/api/v1/management/loan-operations?q=&status=all') {
        return { summary: {}, entries: [], audits: [], notice: '' };
      }
      if (path === '/api/v1/management/past-due/reasons') {
        return { schema_available: true, summary: {}, rows: [] };
      }
      if (path === '/api/v1/management/financial-accounting/statements') {
        return { statements: null };
      }
      if (path === '/api/v1/management/financial-accounting/journals') {
        return { entries: [], can_manage: false, automatic_loan_posting_enabled: false };
      }
      if (path === '/api/v1/management/financial-accounting/trial-balance') {
        return { trial_balance: null };
      }
      if (path === '/api/v1/management/alerts-audit?window_days=30&limit=100') {
        return { alerts: [], events: [] };
      }
      throw new Error(`Unexpected Management request: ${path}`);
    },
  };

  await mountManagementWorkspace({
    api,
    root,
    session: { permissions: ['management.dashboard.view', 'accounting.view'] },
    setNavigation: navigation.setNavigation,
  });

  assert.match(root.innerHTML, /Management workspace/i);
  assert.match(root.innerHTML, /Loan operations/i);
  assert.match(root.innerHTML, /Past-due reasons/i);
  assert.match(root.innerHTML, /Financial statements/i);
  assert.match(root.innerHTML, /General journal & trial balance/i);
  assert.ok(navigation.items.some((item) => item.label === 'Loan operations'));
  assert.ok(navigation.items.some((item) => item.label === 'Past-due reasons'));
  assert.ok(navigation.items.some((item) => item.label === 'Financial statements'));
  assert.ok(navigation.items.some((item) => item.label === 'General journal & trial balance'));
  assert.ok(calls.includes('/api/v1/management/past-due/reasons'));
  assert.ok(calls.includes('/api/v1/management/financial-accounting/statements'));
  assert.ok(calls.includes('/api/v1/management/financial-accounting/journals'));
  assert.ok(calls.includes('/api/v1/management/financial-accounting/trial-balance'));
});
