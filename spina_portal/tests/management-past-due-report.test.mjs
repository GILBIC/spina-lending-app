import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

async function importPastDueModule() {
  try {
    return await import('../assets/management-past-due-report.js');
  } catch {
    return {};
  }
}

test('Management Past-Due Reason Reporting requires management.dashboard.view and stays read-only', () => {
  const withoutDashboard = availableRoleActions('management', ['accounting.view']);
  const withDashboard = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const employee = availableRoleActions('employee', [
    'management.dashboard.view',
  ]);
  const collector = availableRoleActions('collector', [
    'management.dashboard.view',
  ]);

  assert.equal(
    withoutDashboard.some((entry) => entry.key === 'management-past-due-report'),
    false,
  );

  const action = withDashboard.find(
    (entry) => entry.key === 'management-past-due-report',
  );

  assert.ok(action);
  assert.equal(action.path, '/api/v1/management/past-due/reasons');
  assert.equal(action.permission, 'management.dashboard.view');
  assert.equal(Object.hasOwn(action, 'method'), false);
  assert.equal(Object.hasOwn(action, 'financial'), false);

  assert.equal(
    employee.some((entry) => entry.path.includes('/management/past-due/')),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path.includes('/management/past-due/')),
    false,
  );
});

test('Past-Due report loader uses only approved server filters and never exposes UUID filters', async () => {
  const report = await importPastDueModule();
  assert.equal(typeof report.loadManagementPastDueReport, 'function');

  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      return {
        schema_available: true,
        summary: {
          event_count: 0,
          total_past_due_amount: '0.00',
          remaining_past_due_amount: '0.00',
        },
        rows: [],
      };
    },
  };

  await report.loadManagementPastDueReport(api, {
    startDate: '2026-08-01',
    endDate: '2026-08-31',
    area: ' Cardona Proper ',
    reasonCode: 'no_cash',
    eventKind: 'unable_to_pay',
  });

  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/past-due/reasons?start_date=2026-08-01&end_date=2026-08-31&area=Cardona%20Proper&reason_code=no_cash&event_kind=unable_to_pay',
      options: {},
    },
  ]);
  assert.doesNotMatch(calls[0].path, /client_id|collector_user_id|limit=/);
});

test('Past-Due report markup renders server totals and preserves server row order without local aggregation', async () => {
  const report = await importPastDueModule();
  assert.equal(typeof report.managementPastDueReportMarkup, 'function');

  const markup = report.managementPastDueReportMarkup({
    schema_available: true,
    summary: {
      event_count: 44,
      total_past_due_amount: '9876.00',
      remaining_past_due_amount: '4321.00',
    },
    rows: [
      {
        client_name: 'Ana <First>',
        collector_name: 'Collector & One',
        area: 'Cardona <Proper>',
        reason_code: 'no_cash',
        reason_label: 'No cash',
        event_kind: 'unable_to_pay',
        event_kind_label: 'Full Unable to Pay',
        event_count: 2,
        total_past_due_amount: '100.00',
        remaining_past_due_amount: '40.00',
      },
      {
        client_name: 'Bea Second',
        collector_name: 'Collector Two',
        area: 'Iglesia',
        reason_code: 'business_slow',
        reason_label: 'Business slow',
        event_kind: 'partial_payment',
        event_kind_label: 'Partial-payment Past Due',
        event_count: 1,
        total_past_due_amount: '50.00',
        remaining_past_due_amount: '10.00',
      },
    ],
  });

  assert.match(markup, /44/);
  assert.match(markup, /9,876\.00/);
  assert.match(markup, /4,321\.00/);
  assert.match(markup, /Ana &lt;First&gt;/);
  assert.match(markup, /Collector &amp; One/);
  assert.match(markup, /Cardona &lt;Proper&gt;/);
  assert.match(markup, /No cash/);
  assert.match(markup, /Full Unable to Pay/);
  assert.match(markup, /100\.00/);
  assert.match(markup, /40\.00/);
  assert.match(markup, /Business slow/);
  assert.match(markup, /Partial-payment Past Due/);
  assert.ok(markup.indexOf('Ana &lt;First&gt;') < markup.indexOf('Bea Second'));
  assert.doesNotMatch(markup, />150\.00</);
  assert.doesNotMatch(markup, />50\.00<.*>4,321\.00</s);
  assert.doesNotMatch(markup, /data-client-id|data-collector-user-id|Create|Update|Delete|Apply penalty/i);
});

test('Past-Due report markup fails safe when the authoritative schema is unavailable', async () => {
  const report = await importPastDueModule();
  assert.equal(typeof report.managementPastDueReportMarkup, 'function');

  const markup = report.managementPastDueReportMarkup({
    schema_available: false,
    summary: {
      event_count: 0,
      total_past_due_amount: '0.00',
      remaining_past_due_amount: '0.00',
    },
    rows: [],
  });

  assert.match(markup, /not available|unavailable/i);
  assert.doesNotMatch(markup, /Unknown client|Unknown collector/);
});
