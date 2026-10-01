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

const loanPayload = {
  summary: {
    active_loan_count: 3,
    active_client_count: 2,
    active_remaining_total: '12400.00',
    overdue_active_count: 1,
  },
  loans: [
    {
      loan_id: '11111111-1111-4111-8111-111111111111',
      loan_number: 'REG-001',
      client_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      client_code: 'CLIENT-001',
      client_name: 'Maria Client',
      client_area: 'Cardona',
      loan_type_code: 'REG',
      loan_type_name: 'Regular',
      principal: '5000.00',
      remaining_balance: '4800.00',
      daily_amount: '50.00',
      due_date: '2026-11-29',
      loan_status: 'active',
      is_overdue: false,
    },
    {
      loan_id: '22222222-2222-4222-8222-222222222222',
      loan_number: '7X7-001',
      client_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      client_code: 'CLIENT-001',
      client_name: 'Maria Client',
      client_area: 'Cardona',
      loan_type_code: '7X7',
      loan_type_name: '7x7',
      principal: '3000.00',
      remaining_balance: '3000.00',
      daily_amount: '21.00',
      due_date: '2026-11-30',
      loan_status: 'active',
      is_overdue: false,
    },
    {
      loan_id: '33333333-3333-4333-8333-333333333333',
      loan_number: 'REG-002',
      client_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
      client_code: 'CLIENT-002',
      client_name: 'Juan Client',
      client_area: 'Morong',
      loan_type_code: 'REG',
      loan_type_name: 'Regular',
      principal: '5000.00',
      remaining_balance: '4600.00',
      daily_amount: '50.00',
      due_date: '2026-11-28',
      loan_status: 'active',
      is_overdue: true,
    },
  ],
};

function response(path) {
  if (path === '/api/v1/account') return { profile: { full_name: 'Management User' }, devices: [] };
  if (path.startsWith('/api/v1/management/loans')) return loanPayload;
  if (path.startsWith('/api/v1/management/loan-operations')) {
    return { summary: {}, entries: [], audits: [], notice: '' };
  }
  return {};
}

test('Clients & loans groups multiple loans under one Client parent', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const controller = new AbortController();
  try {
    await mountManagementWorkspace({
      root,
      api: { async request(path) { return response(path); } },
      session: { user: { role: 'management', roles: ['management'] }, permissions: [] },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
    });

    const screen = root.querySelector('#management-clients-loans');
    const groups = screen.querySelectorAll('[data-client-loan-group]');
    assert.equal(groups.length, 2);

    const maria = groups.find((group) => group.textContent.includes('Maria Client'));
    assert.ok(maria);
    assert.equal((maria.textContent.match(/Maria Client/g) || []).length, 1);
    assert.match(maria.textContent, /CLIENT-001/);
    assert.match(maria.textContent, /Cardona/);
    assert.match(maria.textContent, /REG-001/);
    assert.match(maria.textContent, /7X7-001/);
    assert.match(maria.textContent, /Regular/);
    assert.match(maria.textContent, /7x7/);
    assert.match(maria.textContent, /₱4,800\.00/);
    assert.match(maria.textContent, /₱3,000\.00/);

    const loanItems = maria.querySelectorAll('[data-client-loan-item]');
    assert.equal(loanItems.length, 2);
  } finally {
    controller.abort();
  }
});

test('Clients & loans uses clear portfolio language and keeps the existing server query contract', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const controller = new AbortController();
  const calls = [];
  try {
    await mountManagementWorkspace({
      root,
      api: {
        async request(path) {
          calls.push(path);
          return response(path);
        },
      },
      session: { user: { role: 'management', roles: ['management'] }, permissions: [] },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
    });

    const screen = root.querySelector('#management-clients-loans');
    assert.match(screen.textContent, /Outstanding balance/i);
    assert.match(screen.textContent, /Overdue loans/i);
    assert.doesNotMatch(screen.textContent, /Remaining portfolio/i);
    assert.doesNotMatch(screen.textContent, /Overdue active/i);
    assert.match(screen.textContent, /Daily amount/i);

    assert.ok(calls.includes('/api/v1/management/loans?status=active'));
    assert.equal(
      calls.some((path) => path.includes('area=') || path.includes('loan_type=')),
      false,
      'the UI must not invent unsupported backend filters',
    );
  } finally {
    controller.abort();
  }
});
