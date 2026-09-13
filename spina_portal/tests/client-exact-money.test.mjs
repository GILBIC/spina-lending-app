import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clientRenewalRows,
  loanCard,
  mountClientWorkspace,
} from '../assets/roles/client.js';

const LARGE_EXACT_MONEY = '90071992547409.93';
const LARGE_EXACT_DISPLAY = '₱90,071,992,547,409.93';

test('Client loan card preserves authoritative money beyond IEEE-754 safe precision', () => {
  const html = loanCard({
    loan_id: 'loan-exact',
    loan_number: 'REG-EXACT',
    loan_type_name: 'Regular',
    principal: LARGE_EXACT_MONEY,
    remaining_balance: LARGE_EXACT_MONEY,
    daily_amount: LARGE_EXACT_MONEY,
    paid_amount: LARGE_EXACT_MONEY,
    date_released: '2026-09-13',
    due_date: '2027-01-11',
    status: 'active',
  });

  assert.equal(html.match(/₱90,071,992,547,409\.93/g)?.length, 4);
});

test('Client official payment row preserves authoritative amount and balance exactly', async () => {
  const root = {
    innerHTML: '',
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
  const responses = new Map([
    ['/api/v1/account', { profile: { full_name: 'Exact Client' }, devices: [] }],
    ['/api/v1/client/loans', { loans: [] }],
    ['/api/v1/client/payments', {
      payments: [{
        collection_date: '2026-09-13',
        loan_number: 'REG-EXACT',
        loan_type_name: 'Regular',
        entry_type: 'payment',
        amount: LARGE_EXACT_MONEY,
        receipt_number: 'R-EXACT',
        official_balance: LARGE_EXACT_MONEY,
        status: 'accepted',
      }],
    }],
    ['/api/v1/client/statement', { client: {}, loans: [], payments: [] }],
    ['/api/v1/client/renewals', { loans: [], requests: [] }],
    ['/api/v1/client/renewal-workflow', { requests: [] }],
    ['/api/v1/client/support', { requests: [] }],
    ['/api/v1/client/gcash/config', { payment_available: false }],
    ['/api/v1/activity-notifications', []],
  ]);
  const api = {
    async request(path) {
      if (!responses.has(path)) throw new Error(`Unexpected request: ${path}`);
      return responses.get(path);
    },
  };

  await mountClientWorkspace({ root, api, setNavigation() {} });

  assert.equal(root.innerHTML.match(/₱90,071,992,547,409\.93/g)?.length, 2);
});

test('Client initial renewal row preserves requested amount exactly', () => {
  const html = clientRenewalRows([{
    request_id: 'renewal-exact',
    loan_number: 'REG-EXACT',
    requested_amount: LARGE_EXACT_MONEY,
    submitted_at: '2026-09-13T00:00:00Z',
    status: 'pending',
  }]);

  assert.match(html, new RegExp(LARGE_EXACT_DISPLAY.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});
