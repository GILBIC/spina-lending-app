import assert from 'node:assert/strict';
import test from 'node:test';

import * as clientModule from '../assets/roles/client.js';

function activeSevenBySevenLoan(overrides = {}) {
  return {
    loan_id: 'seven/active',
    loan_number: '7X7-001',
    loan_type_code: 'seven_by_seven',
    loan_type_name: '7x7',
    status: 'active',
    principal: '3000.00',
    remaining_balance: '89.00',
    daily_amount: '50.00',
    paid_amount: '2911.00',
    ...overrides,
  };
}

function projectedSchedule(overrides = {}) {
  return {
    loan_id: 'seven/active',
    loan_number: '7X7-001',
    loan_type: '7x7',
    calculation_mode: 'seven_by_seven',
    is_7x7: true,
    penalty_status: 'projected',
    projected_penalty: '5.13',
    assessed_penalty_balance: '1.25',
    penalty_base: '89.00',
    remaining_cost_headroom: '4993.62',
    exact_payoff_total: '90071992547409.93',
    management_review_required_reason: '',
    rows: [],
    ...overrides,
  };
}

test('Web Client Home shows exact server payoff for relevant post-maturity 7x7 state', () => {
  const html = clientModule.loanCard(
    activeSevenBySevenLoan(),
    projectedSchedule(),
  );

  assert.match(html, /Exact payoff/);
  assert.match(html, /₱90,071,992,547,409\.93/);
  assert.doesNotMatch(html, /₱90,071,992,547,409\.94/);
});

test('Web Client Home fails closed when Management review is required', () => {
  const html = clientModule.loanCard(
    activeSevenBySevenLoan(),
    projectedSchedule({
      penalty_status: 'management_review_required',
      exact_payoff_total: '0.00',
      management_review_required_reason:
        'Exact signed authority is missing. <script>alert("x")</script>',
    }),
  );

  assert.match(html, /Management review required/);
  assert.match(html, /Exact signed authority is missing\./);
  assert.doesNotMatch(html, /Exact payoff/);
  assert.doesNotMatch(html, /<script>/);
});

test('Web Client Home does not invent a post-maturity amount before it applies', () => {
  const html = clientModule.loanCard(
    activeSevenBySevenLoan(),
    projectedSchedule({
      penalty_status: 'not_applicable',
      projected_penalty: '0.00',
      assessed_penalty_balance: '0.00',
      exact_payoff_total: '0.00',
    }),
  );

  assert.doesNotMatch(html, /Exact payoff/);
  assert.doesNotMatch(html, /Management review required/);
});

test('Web Client Home loads the protected schedule only for active 7x7 loans', async () => {
  const loadSchedules = clientModule.loadClientHomeObligationSchedules;
  assert.equal(typeof loadSchedules, 'function');

  const requestedPaths = [];
  const api = {
    async request(path) {
      requestedPaths.push(path);
      return projectedSchedule();
    },
  };
  const result = await loadSchedules(api, {
    loans: [
      activeSevenBySevenLoan({
        loan_id: 'regular-active',
        loan_type_code: 'regular',
        loan_type_name: 'Regular',
      }),
      activeSevenBySevenLoan(),
      activeSevenBySevenLoan({ loan_id: 'seven-paid', status: 'paid' }),
    ],
  });

  assert.deepEqual(requestedPaths, [
    '/api/v1/client/loans/seven%2Factive/schedule',
  ]);
  assert.equal(result['seven/active'].exact_payoff_total, '90071992547409.93');
});

test('Web Client workspace wires the authoritative Home obligation loader', () => {
  assert.match(
    clientModule.mountClientWorkspace.toString(),
    /loadClientHomeObligationSchedules/,
  );
});
