import assert from 'node:assert/strict';
import test from 'node:test';

import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element } from './helpers/dom.mjs';

class ManagementElement extends Element {
  querySelectorAll(selector) {
    if (/^\[[^\]]+\]\[[^\]]+\]$/.test(selector)) return [];
    return super.querySelectorAll(selector);
  }
}

const metrics = [
  { key: 'portfolio.active_clients', count: 4 },
  { key: 'portfolio.active_loans', count: 7 },
  { key: 'portfolio.overdue_loans', count: 0 },
  { key: 'portfolio.outstanding_balance', amount: '28000.00' },
  { key: 'collections.latest_day', count: 2, amount: '71.00', as_of_date: '2026-09-16' },
  { key: 'collections.unremitted', count: 3, amount: '584.00' },
  { key: 'queues.remittances_assigned', count: 1, amount: '21.00' },
  { key: 'queues.renewals_protected', count: 0 },
  { key: 'queues.staff_registrations', count: 0 },
  { key: 'queues.client_registrations', count: 0 },
  { key: 'queues.collector_mobile_devices', count: 0 },
  { key: 'queues.borrower_support', count: 0 },
  { key: 'activity.unread', count: 2 },
];

function response(path) {
  if (path === '/api/v1/account') {
    return { profile: { full_name: 'Gilbic Clarck San Jose' }, devices: [] };
  }
  if (path === '/api/v1/management/dashboard-overview') {
    return {
      generated_at: '2026-10-01T11:09:00Z',
      currency: 'PHP',
      metrics,
    };
  }
  if (path.startsWith('/api/v1/management/loans')) return { summary: {}, loans: [] };
  if (path.startsWith('/api/v1/management/loan-operations')) {
    return { summary: {}, entries: [], audits: [], notice: '' };
  }
  return {};
}

test('Management overview uses business labels and preserves count plus amount', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const controller = new AbortController();
  try {
    await mountManagementWorkspace({
      root,
      api: { async request(path) { return response(path); } },
      session: {
        user: { role: 'management', roles: ['management'] },
        permissions: ['management.dashboard.view'],
      },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
    });

    const overview = root.querySelector('#management-overview');
    const text = overview.textContent;

    for (const internalKey of metrics.map((metric) => metric.key)) {
      assert.doesNotMatch(text, new RegExp(internalKey.replaceAll('.', '\\.'), 'i'));
    }

    assert.match(text, /Portfolio/);
    assert.match(text, /Collections/);
    assert.match(text, /Needs attention/);

    for (const label of [
      'Active clients',
      'Active loans',
      'Outstanding balance',
      'Latest collections',
      'Unremitted collections',
      'Assigned remittances',
      'Renewal requests',
      'Client support',
      'Unread updates',
    ]) assert.match(text, new RegExp(label, 'i'));

    assert.match(text, /₱71\.00/);
    assert.match(text, /2 payments/);
    assert.match(text, /Sep 16, 2026/);
    assert.match(text, /₱584\.00/);
    assert.match(text, /3 collections/);
    assert.match(text, /₱21\.00/);
    assert.match(text, /1 remittance/);
  } finally {
    controller.abort();
  }
});

test('Management overview copy is operational instead of implementation-oriented', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const controller = new AbortController();
  try {
    await mountManagementWorkspace({
      root,
      api: { async request(path) { return response(path); } },
      session: {
        user: { role: 'management', roles: ['management'] },
        permissions: ['management.dashboard.view'],
      },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
    });

    const overview = root.querySelector('#management-overview').textContent;
    assert.match(overview, /Today's portfolio, collections, and work requiring attention/i);
    assert.match(overview, /Updated/i);
    assert.doesNotMatch(overview, /server-authoritative/i);
    assert.doesNotMatch(overview, /protected queues/i);
  } finally {
    controller.abort();
  }
});
