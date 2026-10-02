import assert from 'node:assert/strict';
import test from 'node:test';

import { mountClientWorkspace } from '../assets/roles/client.js';
import { mountCollectorWorkspace } from '../assets/roles/collector.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element } from './helpers/dom.mjs';

const mounts = {
  client: mountClientWorkspace,
  collector: mountCollectorWorkspace,
  employee: mountEmployeeWorkspace,
  management: mountManagementWorkspace,
};

class RoleElement extends Element {
  querySelectorAll(selector) {
    // These compound selectors bind actions that the empty Client fixture has no rows for.
    if (/^\[[^\]]+\]\[[^\]]+\]$/.test(selector)) return [];
    return super.querySelectorAll(selector);
  }
}

function response(path) {
  if (path === '/api/v1/account') return { profile: { full_name: 'Synthetic User' }, devices: [] };
  if (path === '/api/v1/client/loans') return { loans: [] };
  if (path === '/api/v1/client/payments') return { payments: [] };
  if (path === '/api/v1/client/statement') return { client: {}, loans: [], payments: [] };
  if (path === '/api/v1/client/renewals') return { loans: [], requests: [] };
  if (path === '/api/v1/client/renewal-workflow') return { requests: [] };
  if (path === '/api/v1/client/support') return { requests: [] };
  if (path === '/api/v1/client/gcash/config') return { payment_available: false };
  if (path === '/api/v1/activity-notifications') return [];
  if (path === '/api/v1/management/dashboard-overview') return { metrics: [{ key: 'pending_review', count: 3 }] };
  return {};
}

const scenarios = [
  ...Object.entries(mounts).map(([role, mount]) => ({ role, mount, permissions: [] })),
  { role: 'collector', mount: mountCollectorWorkspace, permissions: ['route.view', 'collection.create', 'remittance.view'] },
  { role: 'employee', mount: mountEmployeeWorkspace, permissions: ['support.manage', 'remittance.view'] },
  { role: 'management', mount: mountManagementWorkspace, permissions: ['renewal.manage', 'support.manage', 'management.dashboard.view'] },
];

for (const { role, mount, permissions } of scenarios) {
  test(`${role} daily screen has reachable sections and only real task links (${permissions.length} permissions)`, async () => {
    const controller = new AbortController();
    const root = new RoleElement();
    root.dataset = {};
    let navigation = [];
    let activated = 0;
    try {
      await mount({
        root,
        api: { async request(path) { return response(path); } },
        session: { user: { role }, permissions },
        signal: controller.signal,
        setNavigation(items) { navigation = items; },
        activateNavigation() { activated += 1; },
      });

      assert.equal(activated, 1, 'selection runs after the full role markup is installed');
      assert.equal(navigation[0].id, `${role}-overview`);
      if (role === 'management') {
        assert.deepEqual(
          navigation.map((item) => item.label),
          ['Today', 'Clients & loans', 'Collections', 'Accounting', 'People & operations', 'Account'],
        );
      } else {
        assert.equal(navigation[0].group, 'Daily work');
      }
      const today = root.querySelector(`#${role}-overview`);
      if (today.innerHTML.includes('metric-grid')) {
        assert.ok(today.innerHTML.indexOf('daily-actions') < today.innerHTML.indexOf('metric-grid'),
          'daily links appear before summary metrics on a narrow screen');
      }
      const sections = root.children.filter((child) => typeof child !== 'string'
        && child.attributes?.['data-workspace-section'] !== undefined);
      const ids = new Set(sections.map((section) => section.attributes.id));
      assert.equal(ids.size, navigation.length, 'each navigation item has one top-level screen');
      for (const item of navigation) assert.ok(ids.has(item.id), item.id);
      for (const link of root.querySelectorAll('.task-link')) {
        assert.ok(ids.has(link.attributes['data-nav-target']), 'quick links target an available screen');
      }
    } finally {
      controller.abort();
    }
  });
}

for (const request of [
  { request_id: 'renewal-decision', status: 'approved' },
  { request_id: 'renewal-sign', status: 'approved', client_decision: 'accepted', signers: [{
    signer_id: 'borrower-signer', party_role: 'borrower', signed: false,
    government_id_verified: true, selfie_verified: true,
  }] },
  { request_id: 'renewal-cash', status: 'approved', client_decision: 'accepted',
    cash_given_to_client_at: '2026-10-01T00:00:00Z' },
]) {
  test(`Client Today links an approved renewal action: ${request.request_id}`, async () => {
    const root = new RoleElement();
    root.dataset = {};
    await mountClientWorkspace({
      root,
      api: { async request(path) {
        if (path === '/api/v1/client/renewal-workflow') return { requests: [request] };
        return response(path);
      } },
      setNavigation() {},
    });
    const today = root.querySelector('#client-overview');
    assert.ok(today.querySelector('[data-nav-target="client-renewals"]'));
    assert.match(today.textContent, /1 action for you/);
    assert.match(today.textContent, /Pending renewals 0/);
  });
}

test('Collector attention list offers the route action without changing the entry', async () => {
  const root = new RoleElement();
  root.dataset = {};
  await mountCollectorWorkspace({
    root,
    session: { user: { role: 'collector' }, permissions: ['route.view'] },
    api: { async request(path) {
      if (path === '/api/v1/collector/routes/today') return {
        route_date: '2026-10-01', entries: [{
          route_entry_id: 'synthetic-entry',client_id:'synthetic-client',loan_id:'synthetic-loan', area: 'Synthetic Area', client_name: 'Synthetic Client',
          loan_type: 'Regular', processed_today: false, daily_amount: '100.00',
        }],
      };
      return response(path);
    } },
    setNavigation() {},
  });
  const review = root.querySelector('#collector-master-review');
  assert.ok(review.querySelector('[data-nav-target="collector-route"]'));
  assert.match(review.textContent, /Synthetic Client/);
});

const failedReads = [
  { role: 'client', mount: mountClientWorkspace, permissions: [], paths: ['/api/v1/client/loans', '/api/v1/client/payments', '/api/v1/client/renewals', '/api/v1/client/support'] },
  { role: 'collector', mount: mountCollectorWorkspace, permissions: ['route.view'], paths: ['/api/v1/collector/routes/today'] },
  { role: 'employee', mount: mountEmployeeWorkspace, permissions: ['support.manage', 'remittance.view'], paths: ['/api/v1/management/support?status=open', '/api/v1/notifications', '/api/v1/activity-notifications'] },
  { role: 'management', mount: mountManagementWorkspace, permissions: ['renewal.manage', 'support.manage'], paths: ['/api/v1/management/renewals?status=pending', '/api/v1/management/support?status=open'] },
];

for (const { role, mount, permissions, paths } of failedReads) {
  test(`${role} Today shows unavailable instead of a false zero after failed reads`, async () => {
    const controller = new AbortController();
    const root = new RoleElement();
    root.dataset = {};
    try {
      await mount({
        root,
        api: { async request(path) {
          if (paths.includes(path)) throw new Error('Synthetic read failure');
          return response(path);
        } },
        session: { user: { role }, permissions },
        signal: controller.signal,
        setNavigation() {},
      });
      const today = root.querySelector(`#${role}-overview`);
      assert.ok(today.textContent.includes('Unavailable') || today.textContent.includes('unavailable'));
      assert.match(today.textContent, /could not load|unavailable/i);
      if (role === 'collector') {
        assert.doesNotMatch(root.querySelector('#collector-master-review').textContent, /Route review clear/);
      }
    } finally {
      controller.abort();
    }
  });
}


test('Management keeps detailed tools inside six high-level workspace sections', async () => {
  const controller = new AbortController();
  const root = new RoleElement();
  root.dataset = {};
  let navigation = [];
  try {
    await mountManagementWorkspace({
      root,
      api: { async request(path) { return response(path); } },
      session: {
        user: { role: 'management' },
        permissions: [
          'management.dashboard.view',
          'client_onboarding.requirement.review',
          'renewal.manage',
          'support.manage',
          'client_payment_proof.review',
          'collection.create',
          'collection.correct',
          'accounting.view',
          'area.manage',
          'account.manage',
          'device.manage',
        ],
      },
      signal: controller.signal,
      setNavigation(items) { navigation = items; },
      activateNavigation() {},
    });

    assert.deepEqual(
      navigation.map((item) => item.id),
      [
        'management-overview',
        'management-clients-loans',
        'management-collections',
        'management-accounting-hub',
        'management-operations',
        'management-account',
      ],
    );
    const topLevel = root.children.filter((child) => typeof child !== 'string'
      && child.attributes?.['data-workspace-section'] !== undefined);
    assert.deepEqual(
      topLevel.map((section) => section.attributes.id),
      navigation.map((item) => item.id),
    );
    assert.ok(root.querySelector('#management-renewals'));
    assert.ok(root.querySelector('#management-loan-operations'));
    assert.ok(root.querySelector('#management-financial-statements'));
    assert.ok(root.querySelector('#management-staff'));
    for (const link of root.querySelector('#management-overview').querySelectorAll('.task-link')) {
      assert.ok(navigation.some((item) => item.id === link.attributes['data-nav-target']));
    }
  } finally {
    controller.abort();
  }
});
