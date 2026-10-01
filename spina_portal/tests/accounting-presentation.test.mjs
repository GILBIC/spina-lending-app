import assert from 'node:assert/strict';
import test from 'node:test';

import { mountManagementAccounting } from '../assets/management-accounting.js';
import { mountCollectorOtherArea } from '../assets/collector-other-area.js';
import { Element } from './helpers/dom.mjs';

const period = '00000000-0000-4000-8000-000000000001';
const session = {
  user: { id: 'manager', role: 'Management', roles: ['management'] },
  permissions: ['accounting.view', 'accounting.period.manage', 'collection.create'],
};

const overview = {
  notice: 'Protected accounting service notice.',
  period_management_enabled: true,
  fiscal_periods: [{
    period_id: period,
    label: 'August 2026',
    start_date: '2026-08-01',
    end_date: '2026-08-31',
    status: 'open',
    posted_journal_count: 2,
    draft_journal_count: 0,
  }],
  accounts: [{ code: '1100', name: 'Cash on hand', account_type: 'asset', normal_balance: 'debit', is_posting: true, is_active: true }],
  policies: [{ name: 'Regular loan', operational_rule: 'Contract schedule', accounting_rule: 'Effective interest evidence', renewal_rule: 'Reviewed renewal' }],
  summary: {
    active_loan_count: 7,
    active_principal: '29000.00',
    operational_outstanding: '28000.00',
    unremitted_cash: '584.00',
    received_remittance_total: '563.00',
  },
  foundation: { posted_journal_count: 2, draft_journal_count: 0 },
  cutover: {
    summary: { overall_status: 'blocked' },
    loans: [{
      loan_number: 'TEST-REG-1',
      client_name: 'Test Client',
      readiness_status: 'contract_validation_required',
      blockers: ['Missing approved source contract'],
    }],
  },
};

test('Accounting workflows are grouped into four clear navigation areas without changing workflow IDs', async () => {
  const root = new Element();
  const controller = new AbortController();
  try {
    await mountManagementAccounting({
      root,
      api: { request: async () => overview },
      session,
      signal: controller.signal,
    });

    const groups = root.querySelectorAll('[data-accounting-group]');
    assert.deepEqual(
      groups.map((group) => group.getAttribute('data-accounting-group')),
      ['overview', 'periods', 'opening', 'ecl'],
    );
    assert.match(groups[0].textContent, /Overview/);
    assert.match(groups[1].textContent, /Periods & close/);
    assert.match(groups[2].textContent, /Opening & cutover/);
    assert.match(groups[3].textContent, /ECL & tax/);

    for (const workflow of ['periods','close','capital','workbook','opening','measurement','outcomes','tax']) {
      assert.ok(root.querySelector(`[data-accounting-tab="${workflow}"]`), workflow);
    }
  } finally {
    controller.abort();
  }
});

test('Accounting overview uses operational language and surfaces blocked cutover readiness', async () => {
  const root = new Element();
  const controller = new AbortController();
  try {
    await mountManagementAccounting({
      root,
      api: { request: async () => overview },
      session,
      signal: controller.signal,
    });

    assert.match(root.textContent, /Current financial position/i);
    assert.doesNotMatch(root.textContent, /Operational source summary/i);
    assert.match(root.textContent, /Accounting readiness needs attention/i);

    const readiness = root.querySelector('[data-accounting-cutover-alert]');
    assert.ok(readiness);
    assert.match(readiness.textContent, /Blocked/i);
    assert.match(readiness.textContent, /Review blockers/i);
    assert.match(readiness.textContent, /Missing approved source contract/i);

    assert.match(root.textContent, /Create fiscal period/i);
    assert.match(root.textContent, /Send period for review/i);
    assert.doesNotMatch(root.textContent, /Review new fiscal period/i);
    assert.doesNotMatch(root.textContent, /Move to review/i);
    assert.match(root.textContent, /Refresh/);
    assert.doesNotMatch(root.textContent, /Reload authoritative records/i);
  } finally {
    controller.abort();
  }
});

test('Management direct-payment copy explains the user task without internal ownership wording', () => {
  const root = new Element();
  const controller = new AbortController();
  const guard = {
    current: true,
    locked: false,
    begin: () => true,
    finish() {},
    sync() {},
  };

  const dispose = mountCollectorOtherArea({
    root,
    api: { request: async () => [] },
    session: { user: { role: 'management' }, permissions: ['collection.create'] },
    routeDate: '2026-10-01',
    guard,
    identity: () => ({}),
    onSaved: async () => {},
    signal: controller.signal,
    mode: 'management',
  });

  assert.match(root.textContent, /Record a payment for a client outside the assigned route/i);
  assert.match(root.textContent, /assigned Collector remains unchanged/i);
  assert.doesNotMatch(root.textContent, /You remain the recorder/i);
  assert.doesNotMatch(root.textContent, /cash custody are preserved/i);

  dispose();
  controller.abort();
});
