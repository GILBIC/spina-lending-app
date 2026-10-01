import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { Element, fire } from './helpers/dom.mjs';

const module = await import('../assets/management-alerts-audit.js').catch(() => ({}));
const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);
const serviceWorkerSource = await readFile(
  new URL('../sw.js', import.meta.url),
  'utf8',
);

const snapshot = {
  generated_at: '2026-10-01T16:35:00+08:00',
  window_days: 30,
  limit: 100,
  currency: 'PHP',
  visible_domains: [
    'payment_updates',
    'approvals',
    'remittance_custody',
    'financial',
  ],
  alerts: [
    {
      code: 'payment_updates_unread',
      domain: 'payment_updates',
      title: 'Unread payment updates',
      count: 2,
      severity: 'info',
      navigation_code: 'payment_updates',
    },
    {
      code: 'assigned_remittances',
      domain: 'remittance_custody',
      title: 'Remittances assigned for review',
      count: 1,
      amount: '21.00',
      severity: 'review',
      navigation_code: 'remittance_review',
    },
  ],
  events: [
    {
      event_key: 'event-1',
      domain: 'approvals',
      action_code: 'device.status_change',
      title: 'Device status changed',
      severity: 'attention',
      navigation_code: 'staff_devices',
      occurred_at: '2026-10-01T16:35:00+08:00',
      business_date: '2026-10-01',
      record_id: '11111111-1111-4111-8111-111111111111',
      reference: 'collector',
      current_state: 'revoked',
      actor_name: 'Gilbic Clarck San Jose',
      checker_name: null,
      source_type: null,
      source_label: null,
      reason: null,
    },
    {
      event_key: 'event-2',
      domain: 'approvals',
      action_code: 'device.status_change',
      title: 'Device status changed',
      severity: 'attention',
      navigation_code: 'staff_devices',
      occurred_at: '2026-10-01T16:27:00+08:00',
      business_date: '2026-10-01',
      record_id: '22222222-2222-4222-8222-222222222222',
      reference: 'Gilbic',
      current_state: 'active',
      actor_name: 'Gilbic Clarck San Jose',
      checker_name: null,
      source_type: null,
      source_label: null,
      reason: null,
    },
    {
      event_key: 'event-3',
      domain: 'financial',
      action_code: 'financial.posted',
      title: 'Protected journal posted',
      severity: 'attention',
      navigation_code: 'financial_accounting',
      occurred_at: '2026-09-30T15:00:00+08:00',
      business_date: '2026-09-30',
      record_id: '33333333-3333-4333-8333-333333333333',
      reference: 'JE-202609-00000001',
      current_state: 'posted',
      actor_name: 'Manager One',
      checker_name: 'Manager Two',
      source_type: 'manual',
      source_label: 'Manual journal',
      reason: 'Reviewed evidence complete',
    },
  ],
  event_total_count: 5,
  notice: 'Read-only visibility. Complete approvals, corrections, and postings in their owning Management workflows.',
};

test('Alerts & Audit renders human domain labels and snapshot context', () => {
  assert.equal(typeof module.managementAlertsAuditMarkup, 'function');
  const root = new Element();
  root.innerHTML = module.managementAlertsAuditMarkup(snapshot);

  for (const label of [
    'All',
    'Payment updates',
    'Approvals',
    'Remittance & custody',
    'Financial',
  ]) assert.match(root.textContent, new RegExp(label.replace('&', '&(?:amp;)?')));

  assert.match(root.textContent, /5 authorized events/i);
  assert.match(root.textContent, /Last 30 days/i);
  assert.match(root.textContent, /Updated/i);
  assert.doesNotMatch(root.textContent, /payment_updates|remittance_custody/);
  assert.match(root.textContent, /Review alerts and permanent audit history/i);
});

test('Alerts use only safe existing Management destinations', () => {
  assert.equal(typeof module.managementAlertNavigationTarget, 'function');

  assert.equal(module.managementAlertNavigationTarget('staff_devices'), 'management-operations');
  assert.equal(module.managementAlertNavigationTarget('client_registrations'), 'management-clients-loans');
  assert.equal(module.managementAlertNavigationTarget('renewals'), 'management-clients-loans');
  assert.equal(module.managementAlertNavigationTarget('support'), 'management-operations');
  assert.equal(module.managementAlertNavigationTarget('remittance_review'), 'management-collections');
  assert.equal(module.managementAlertNavigationTarget('financial_accounting'), 'management-accounting-hub');
  assert.equal(module.managementAlertNavigationTarget('payment_updates'), null);
  assert.equal(module.managementAlertNavigationTarget('unknown_code'), null);

  const root = new Element();
  root.innerHTML = module.managementAlertsAuditMarkup(snapshot);

  const remittance = root.querySelector('[data-alert-code="assigned_remittances"]');
  assert.equal(remittance.getAttribute('data-nav-target'), 'management-collections');
  assert.match(remittance.textContent, /1/);
  assert.match(remittance.textContent, /₱21\.00/);

  const payments = root.querySelector('[data-alert-code="payment_updates_unread"]');
  assert.equal(payments.getAttribute('data-nav-target'), null);
  assert.match(payments.textContent, /2/);
});

test('Audit events remain individual permanent records and use compact business facts', () => {
  const root = new Element();
  root.innerHTML = module.managementAlertsAuditMarkup(snapshot);

  const events = root.querySelectorAll('[data-audit-event-key]');
  assert.equal(events.length, 3);
  assert.equal(
    events.filter((event) => event.textContent.includes('Device status changed')).length,
    2,
    'repeated authoritative device events must not be deduplicated',
  );

  const first = root.querySelector('[data-audit-event-key="event-1"]');
  assert.match(first.textContent, /Device status changed/);
  assert.match(first.textContent, /collector/);
  assert.match(first.textContent, /revoked/i);
  assert.match(first.textContent, /Gilbic Clarck San Jose/);
  assert.equal(first.getAttribute('data-nav-target'), 'management-operations');

  const financial = root.querySelector('[data-audit-event-key="event-3"]');
  assert.match(financial.textContent, /JE-202609-00000001/);
  assert.match(financial.textContent, /Manual journal/);
  assert.match(financial.textContent, /Maker: Manager One/i);
  assert.match(financial.textContent, /Checker: Manager Two/i);
  assert.match(financial.textContent, /Reviewed evidence complete/i);
});

test('domain chips filter locally without requesting or changing server event order', () => {
  assert.equal(typeof module.bindManagementAlertsAudit, 'function');
  const root = new Element();
  root.innerHTML = module.managementAlertsAuditMarkup(snapshot);

  const cleanup = module.bindManagementAlertsAudit(root);
  const approvals = root.querySelector('[data-alert-domain-filter="approvals"]');
  fire(approvals, 'click');

  const approvalItems = root.querySelectorAll('[data-alert-domain="approvals"]');
  const financialItems = root.querySelectorAll('[data-alert-domain="financial"]');
  const paymentItems = root.querySelectorAll('[data-alert-domain="payment_updates"]');

  assert.ok(approvalItems.length > 0);
  assert.equal(approvalItems.every((item) => item.getAttribute('hidden') === null), true);
  assert.equal(financialItems.every((item) => item.getAttribute('hidden') === ''), true);
  assert.equal(paymentItems.every((item) => item.getAttribute('hidden') === ''), true);
  assert.equal(approvals.getAttribute('aria-pressed'), 'true');

  fire(root.querySelector('[data-alert-domain-filter="all"]'), 'click');
  assert.equal(
    root.querySelectorAll('[data-alert-domain]').every((item) => item.getAttribute('hidden') === null),
    true,
  );

  cleanup();
});

test('Management integrates the isolated Alerts & Audit presenter without changing the protected endpoint', () => {
  assert.match(managementSource, /management-alerts-audit\.js/);
  assert.match(managementSource, /managementAlertsAuditMarkup\(alerts\.data\)/);
  assert.match(managementSource, /bindManagementAlertsAudit/);
  assert.match(
    managementSource,
    /\/api\/v1\/management\/alerts-audit\?window_days=30&limit=100/,
  );
});

test('installed Web shell precaches the isolated Alerts & Audit dependency', () => {
  assert.match(serviceWorkerSource, /'\/assets\/management-alerts-audit\.js'/);
});

test('audit snapshot order and unknown navigation remain read-only after filter cleanup', () => {
  const root = new Element();
  root.innerHTML = module.managementAlertsAuditMarkup({ ...snapshot,
    events: [...snapshot.events, { ...snapshot.events[0], event_key: 'event-4', navigation_code: 'constructor',
      title: '<script>Private</script>' }],
  });
  assert.deepEqual(root.querySelectorAll('[data-audit-event-key]').map((item) => item.getAttribute('data-audit-event-key')),
    ['event-1', 'event-2', 'event-3', 'event-4']);
  assert.equal(root.querySelector('[data-audit-event-key="event-4"]').getAttribute('data-nav-target'), null);
  assert.equal(root.querySelector('script'), null);
  const controller = new AbortController();
  const cleanup = module.bindManagementAlertsAudit(root, { signal: controller.signal });
  const chip = root.querySelector('[data-alert-domain-filter="financial"]');
  controller.abort();
  fire(chip, 'click');
  assert.equal(root.querySelectorAll('[data-alert-domain]').every((item) => item.getAttribute('hidden') === null), true);
  cleanup();
});
