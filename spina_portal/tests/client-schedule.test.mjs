import assert from 'node:assert/strict';
import test from 'node:test';

import { renderClientSchedule } from '../assets/client-schedule.js';

test('Client schedule renderer shows only authoritative server schedule values', () => {
  const html = renderClientSchedule({
    loan_id: 'loan-1',
    loan_number: 'REG-001',
    loan_type: 'Regular',
    is_7x7: false,
    contractual_maturity: '2026-10-10',
    operational_maturity: '2026-10-12',
    maturity_status: 'extended',
    past_due_amount: '200.00',
    rows: [
      {
        payment_date: '2026-09-12',
        amount: '200.00',
        status: 'Due Today',
        details: {
          remaining_amount: '150.00',
          note: 'Management-approved extension',
        },
      },
    ],
  });

  assert.match(html, /Authoritative SPINA schedule/);
  assert.match(html, /Oct 10, 2026/);
  assert.match(html, /Oct 12, 2026/);
  assert.match(html, /₱200\.00/);
  assert.match(html, /Sep 12, 2026/);
  assert.match(html, /Due Today/);
  assert.match(html, /₱150\.00/);
  assert.match(html, /Management-approved extension/);
});

test('Client schedule renderer escapes server notes before displaying them', () => {
  const html = renderClientSchedule({
    loan_type: '7x7',
    is_7x7: true,
    rows: [
      {
        payment_date: '2026-09-13',
        amount: '50.00',
        status: 'Scheduled',
        details: {
          remaining_amount: '50.00',
          note: '<script>alert("x")</script>',
        },
      },
    ],
  });

  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;alert\(&quot;x&quot;\)&lt;\/script&gt;/);
});
