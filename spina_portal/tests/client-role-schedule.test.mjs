import assert from 'node:assert/strict';
import test from 'node:test';

import { loanCard } from '../assets/roles/client.js';

test('Client loan card exposes an on-demand authoritative schedule action', () => {
  const html = loanCard({
    loan_id: 'loan-1',
    loan_number: 'REG-001',
    loan_type_name: 'Regular',
    principal: '5000.00',
    remaining_balance: '4950.00',
    daily_amount: '50.00',
    paid_amount: '50.00',
    date_released: '2026-08-01',
    due_date: '2026-11-29',
    status: 'active',
    pass_count: 0,
    advance_until: null,
  });

  assert.match(html, /data-client-schedule-loan="loan-1"/);
  assert.match(html, />View schedule</);
  assert.match(html, /data-client-schedule-panel/);
});
