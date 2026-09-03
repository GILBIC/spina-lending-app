import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildClientViewModel,
  buildCollectorRouteViewModel,
  buildEmployeeViewModel,
  buildManagementViewModel,
} from '../assets/presenters.js';

test('Client view keeps Regular and 7x7 loans in distinct collections', () => {
  const model = buildClientViewModel({
    account: { profile: { full_name: 'Maria Client' } },
    loans: {
      client: { client_name: 'Maria Client' },
      loans: [
        { loan_id: 'reg-1', loan_type_name: 'Regular', remaining_balance: '5000.00', status: 'active' },
        { loan_id: '7-1', loan_type_name: '7x7', remaining_balance: '1200.00', status: 'active' },
      ],
    },
    payments: { payments: [{ receipt_number: 'R-1', amount: '100.00' }] },
    renewals: { requests: [{ request_id: 'rr-1', status: 'pending' }] },
    support: { requests: [{ request_id: 'sr-1', status: 'open' }] },
    gcash: { payment_available: false, message: 'Coming soon' },
    notifications: [{ notification_id: 'n-1' }],
  });

  assert.equal(model.displayName, 'Maria Client');
  assert.deepEqual(model.regularLoans.map((loan) => loan.loan_id), ['reg-1']);
  assert.deepEqual(model.sevenBySevenLoans.map((loan) => loan.loan_id), ['7-1']);
  assert.equal(model.activeLoanCount, 2);
  assert.equal(model.pendingRenewalCount, 1);
  assert.equal(model.openSupportCount, 1);
  assert.equal(model.paymentInstructions.payment_available, false);
});

test('Collector route preserves server area order and identifies every unresolved entry', () => {
  const model = buildCollectorRouteViewModel({
    route_date: '2026-09-03',
    areas: ['AREA B', 'AREA A'],
    expected_total: '250.00',
    entries: [
      { route_entry_id: 'b-1', area: 'AREA B', client_name: 'Done', processed_today: true, loan_type: 'Regular' },
      { route_entry_id: 'a-1', area: 'AREA A', client_name: 'Waiting', processed_today: false, loan_type: '7x7' },
      { route_entry_id: 'a-2', area: 'AREA A', client_name: 'Short', processed_today: true, attention_required: true, attention_reason: 'Short PHP 50', loan_type: 'Regular' },
    ],
  });

  assert.deepEqual(model.areaGroups.map((group) => group.name), ['AREA B', 'AREA A']);
  assert.deepEqual(model.unresolved.map((entry) => entry.route_entry_id), ['a-1', 'a-2']);
  assert.equal(model.processedCount, 2);
  assert.equal(model.totalCount, 3);
  assert.equal(model.expectedTotal, '250.00');
});

test('Employee view exposes permitted connected work and labels unconnected work honestly', () => {
  const model = buildEmployeeViewModel({
    session: { user: { full_name: 'Office Employee', permissions: ['support.manage'] } },
    account: { profile: { full_name: 'Office Employee' } },
    notifications: [{ notification_id: 'n-1' }],
    support: { requests: [{ request_id: 's-1', status: 'open' }] },
  });

  assert.equal(model.displayName, 'Office Employee');
  assert.ok(model.connectedActions.some((action) => action.key === 'employee-support'));
  assert.equal(model.connectedActions.some((action) => action.key === 'employee-remittance'), false);
  assert.deepEqual(model.unavailable.map((item) => item.key), ['attendance', 'payroll', 'leave']);
  assert.equal(model.openSupportCount, 1);
});

test('Management view maps server metrics and pending queues without inventing values', () => {
  const model = buildManagementViewModel({
    account: { profile: { full_name: 'Management One' } },
    overview: {
      generated_at: '2026-09-03T00:00:00Z',
      metrics: [
        { key: 'active_clients', count: 120 },
        { key: 'unremitted_cash', amount: '5500.00' },
      ],
    },
    loans: { summary: { active_loan_count: 150 }, loans: [{ loan_id: 'l-1' }] },
    alerts: { alerts: [{ code: 'renewals', count: 4 }], events: [{ event_key: 'e-1' }] },
    renewals: { requests: [{ request_id: 'r-1' }] },
    support: { requests: [{ request_id: 's-1' }] },
    registrations: { registrations: [{ user_id: 'u-1' }] },
  });

  assert.equal(model.displayName, 'Management One');
  assert.deepEqual(model.metrics, [
    { key: 'active_clients', count: 120 },
    { key: 'unremitted_cash', amount: '5500.00' },
  ]);
  assert.equal(model.loanSummary.active_loan_count, 150);
  assert.equal(model.pendingRenewals.length, 1);
  assert.equal(model.openSupport.length, 1);
  assert.equal(model.pendingRegistrations.length, 1);
  assert.equal(model.recentEvents.length, 1);
});
