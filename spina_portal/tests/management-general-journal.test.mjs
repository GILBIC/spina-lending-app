import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

async function importJournalModule() {
  try {
    return await import('../assets/management-general-journal.js');
  } catch {
    return {};
  }
}

test('Management General Journal requires accounting.view and stays read-only in Web', () => {
  const withoutAccounting = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const withAccounting = availableRoleActions('management', [
    'management.dashboard.view',
    'accounting.view',
    'accounting.journal.manage',
  ]);
  const employee = availableRoleActions('employee', ['accounting.view']);
  const collector = availableRoleActions('collector', ['accounting.view']);

  assert.equal(
    withoutAccounting.some((entry) => entry.key === 'management-general-journal'),
    false,
  );

  const action = withAccounting.find(
    (entry) => entry.key === 'management-general-journal',
  );

  assert.ok(action);
  assert.equal(
    action.path,
    '/api/v1/management/financial-accounting/journals',
  );
  assert.equal(action.permission, 'accounting.view');
  assert.equal(Object.hasOwn(action, 'method'), false);
  assert.equal(Object.hasOwn(action, 'financial'), false);

  assert.equal(
    employee.some((entry) => entry.path.includes('/financial-accounting/journals')),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path.includes('/financial-accounting/journals')),
    false,
  );
});

test('General Journal loaders use only the existing protected read endpoints', async () => {
  const journal = await importJournalModule();
  assert.equal(typeof journal.loadManagementGeneralJournal, 'function');
  assert.equal(typeof journal.loadManagementTrialBalance, 'function');

  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path.endsWith('/journals')) {
        return {
          entries: [],
          can_manage: true,
          automatic_loan_posting_enabled: false,
        };
      }
      return {
        trial_balance: {
          period_id: 'period-1',
          period_label: 'September 2026',
          total_debits: '1.00',
          total_credits: '1.00',
          balanced: true,
          lines: [],
        },
      };
    },
  };

  const journals = await journal.loadManagementGeneralJournal(api);
  const trialBalance = await journal.loadManagementTrialBalance(api);

  assert.equal(journals.can_manage, true);
  assert.equal(trialBalance.trial_balance.period_label, 'September 2026');
  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/financial-accounting/journals',
      options: {},
    },
    {
      path: '/api/v1/management/financial-accounting/trial-balance',
      options: {},
    },
  ]);
});

test('General Journal markup renders authoritative server values and no mutation controls', async () => {
  const journal = await importJournalModule();
  assert.equal(typeof journal.managementGeneralJournalMarkup, 'function');

  const markup = journal.managementGeneralJournalMarkup({
    journals: {
      entries: [
        {
          entry_id: 'entry-1',
          entry_number: 'GJ-2026-001',
          period_id: 'period-1',
          period_label: 'September 2026',
          posting_date: '2026-09-12',
          description: 'Server <journal> & evidence',
          status: 'posted',
          source_type: 'manual',
          source_reference: 'REF-1',
          reversal_of_entry_id: null,
          created_by_name: 'Manager <One>',
          posted_by_name: 'Manager & Two',
          created_at: '2026-09-12T09:00:00+08:00',
          posted_at: '2026-09-12T09:05:00+08:00',
          total_debit: '987.65',
          total_credit: '987.65',
          lines: [
            {
              line_number: 1,
              account_code: '1100',
              account_name: 'Cash <Main>',
              description: 'Debit line',
              debit: '11.00',
              credit: '0.00',
            },
            {
              line_number: 2,
              account_code: '4100',
              account_name: 'Interest & Fees',
              description: 'Credit line',
              debit: '0.00',
              credit: '22.00',
            },
          ],
        },
      ],
      can_manage: true,
      automatic_loan_posting_enabled: false,
    },
    trialBalance: {
      trial_balance: {
        period_id: 'period-1',
        period_label: 'September 2026',
        total_debits: '7777.00',
        total_credits: '6666.00',
        balanced: false,
        lines: [
          {
            account_code: '1100',
            account_name: 'Cash <Main>',
            account_type: 'asset',
            normal_balance: 'debit',
            total_debit: '44.00',
            total_credit: '0.00',
            debit_balance: '55.00',
            credit_balance: '0.00',
          },
        ],
      },
    },
  });

  assert.match(markup, /GJ-2026-001/);
  assert.match(markup, /September 2026/);
  assert.match(markup, /987\.65/);
  assert.match(markup, /7,777\.00/);
  assert.match(markup, /6,666\.00/);
  assert.match(markup, /Server &lt;journal&gt; &amp; evidence/);
  assert.match(markup, /Manager &lt;One&gt;/);
  assert.match(markup, /Manager &amp; Two/);
  assert.match(markup, /Cash &lt;Main&gt;/);
  assert.match(markup, /Interest &amp; Fees/);
  assert.doesNotMatch(markup, />33\.00</);
  assert.doesNotMatch(markup, />99\.00</);
  assert.doesNotMatch(markup, /Create journal|Edit journal|Post journal|Reverse journal|Cancel draft/i);
});
