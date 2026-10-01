import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { managementPastDueReportMarkup } from '../assets/management-past-due-report.js';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);

test('Past-Due filters have visible business labels without changing protected field names', () => {
  assert.match(managementSource, /<label[^>]*>\s*Start date[\s\S]*name="start_date"/);
  assert.match(managementSource, /<label[^>]*>\s*End date[\s\S]*name="end_date"/);
  assert.match(managementSource, /<label[^>]*>\s*Area[\s\S]*name="area"/);
  assert.match(managementSource, /<label[^>]*>\s*Reason[\s\S]*name="reason_code"/);
  assert.match(managementSource, /<label[^>]*>\s*Event[\s\S]*name="event_kind"/);
  assert.match(managementSource, /value="unable_to_pay">Unable to pay</);
  assert.match(managementSource, /value="partial_payment">Partial payment</);
  assert.doesNotMatch(managementSource, />Full Unable to Pay</);
  assert.doesNotMatch(managementSource, />Partial-payment Past Due</);
});

test('all-zero Past-Due report uses one compact zero state instead of three zero cards', () => {
  const markup = managementPastDueReportMarkup({
    schema_available: true,
    summary: {
      event_count: 0,
      total_past_due_amount: '0.00',
      remaining_past_due_amount: '0.00',
    },
    rows: [],
  });

  assert.match(markup, /data-past-due-zero/);
  assert.match(markup, /No past-due reasons found for these filters/i);
  assert.doesNotMatch(markup, /metric-card/);
  assert.doesNotMatch(markup, /Reason summary/i);
  assert.doesNotMatch(markup, /Server-returned Client/i);
});

test('non-empty Past-Due report uses clearer labels and keeps exact server values', () => {
  const markup = managementPastDueReportMarkup({
    schema_available: true,
    summary: {
      event_count: 3,
      total_past_due_amount: '150.00',
      remaining_past_due_amount: '60.00',
    },
    rows: [{
      client_name: 'Ana First',
      collector_name: 'Collector One',
      area: 'Cardona',
      reason_code: 'no_cash',
      reason_label: 'No cash',
      event_kind: 'unable_to_pay',
      event_kind_label: 'Full Unable to Pay',
      event_count: 2,
      total_past_due_amount: '100.00',
      remaining_past_due_amount: '40.00',
    }, {
      client_name: 'Bea Second',
      collector_name: 'Collector Two',
      area: 'Morong',
      reason_code: 'business_slow',
      reason_label: 'Business slow',
      event_kind: 'partial_payment',
      event_kind_label: 'Partial-payment Past Due',
      event_count: 1,
      total_past_due_amount: '50.00',
      remaining_past_due_amount: '20.00',
    }],
  });

  assert.match(markup, /Past-due events/);
  assert.match(markup, /Amount past due/);
  assert.match(markup, /Still past due/);
  assert.match(markup, /₱150\.00/);
  assert.match(markup, /₱60\.00/);
  assert.match(markup, /Reasons by client and area/);
  assert.ok(markup.indexOf('Ana First') < markup.indexOf('Bea Second'));
  assert.match(markup, /100\.00/);
  assert.match(markup, /40\.00/);
  assert.match(markup, /50\.00/);
  assert.match(markup, /20\.00/);
  assert.doesNotMatch(markup, />150\.00<.*>60\.00<.*>100\.00/s);
});

test('Past-Due result table is marked for responsive cards and keeps row facts labelled', () => {
  const markup = managementPastDueReportMarkup({
    schema_available: true,
    summary: {
      event_count: 1,
      total_past_due_amount: '25.00',
      remaining_past_due_amount: '10.00',
    },
    rows: [{
      client_name: 'Client One',
      collector_name: 'Collector One',
      area: 'Cardona',
      reason_label: 'Emergency',
      event_kind_label: 'Full Unable to Pay',
      event_count: 1,
      total_past_due_amount: '25.00',
      remaining_past_due_amount: '10.00',
    }],
  });

  assert.match(markup, /class="mobile-card-table past-due-table"/);
  for (const label of ['Client','Collector / Area','Reason','Event','Count','Amount past due','Still past due']) {
    assert.match(markup, new RegExp(`data-label="${label.replace('/', '\\/')}"`));
  }
});

test('Past-Due notice is concise while preserving read-only meaning', () => {
  const markup = managementPastDueReportMarkup({
    schema_available: true,
    summary: {
      event_count: 1,
      total_past_due_amount: '25.00',
      remaining_past_due_amount: '10.00',
    },
    rows: [],
  });

  assert.match(markup, /Read-only report/i);
  assert.match(markup, /SPINA records/i);
  assert.doesNotMatch(markup, /protected SPINA server/i);
  assert.doesNotMatch(markup, /This Web view does not calculate delinquency, penalties, balances, or schedules/i);
});
