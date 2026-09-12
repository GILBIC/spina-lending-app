import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);

async function importStatementsModule() {
  try {
    return await import('../assets/management-financial-statements.js');
  } catch {
    return {};
  }
}

test('Management Financial Statements require accounting.view and remain unavailable to Employee', () => {
  const withoutAccounting = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const withAccounting = availableRoleActions('management', [
    'management.dashboard.view',
    'accounting.view',
  ]);
  const employee = availableRoleActions('employee', ['accounting.view']);

  assert.equal(
    withoutAccounting.some((entry) => entry.key === 'management-financial-statements'),
    false,
  );
  assert.ok(
    withAccounting.some(
      (entry) =>
        entry.key === 'management-financial-statements' &&
        entry.path === '/api/v1/management/financial-accounting/statements' &&
        entry.permission === 'accounting.view',
    ),
  );
  assert.equal(
    employee.some((entry) => entry.path.includes('/financial-accounting/statements')),
    false,
  );
});

test('Financial Statements loader uses only the existing protected statement endpoint', async () => {
  const statements = await importStatementsModule();
  assert.equal(typeof statements.loadManagementFinancialStatements, 'function');

  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      return { statements: { period: { label: 'August 2026' } } };
    },
  };

  const result = await statements.loadManagementFinancialStatements(api);

  assert.equal(result.statements.period.label, 'August 2026');
  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/financial-accounting/statements',
      options: {},
    },
  ]);
});

test('Financial Statements markup displays server totals without recomputing accounting values', async () => {
  const statements = await importStatementsModule();
  assert.equal(typeof statements.financialStatementsMarkup, 'function');

  const markup = statements.financialStatementsMarkup({
    statements: {
      period: {
        label: 'August 2026',
        start_date: '2026-08-01',
        end_date: '2026-08-31',
        status: 'closed',
      },
      profit_or_loss: {
        income_lines: [
          { account_code: '4100', account_name: 'Interest Income', amount: '100.00' },
        ],
        expense_lines: [
          { account_code: '5100', account_name: 'Operating Expense', amount: '40.00' },
        ],
        total_income: '1250.00',
        total_expenses: '875.00',
        net_income: '777.00',
      },
      financial_position: {
        as_of_date: '2026-08-31',
        asset_lines: [
          { account_code: '1100', account_name: 'Cash', amount: '500.00' },
        ],
        liability_lines: [
          { account_code: '2100', account_name: 'Payables', amount: '200.00' },
        ],
        equity_lines: [
          { account_code: '3100', account_name: 'Capital', amount: '300.00' },
        ],
        total_assets: '4321.00',
        total_liabilities: '1111.00',
        recorded_equity: '2222.00',
        unclosed_earnings_to_date: '333.00',
        total_equity: '3210.00',
        total_liabilities_and_equity: '4321.00',
        balanced: true,
      },
      source: 'posted_general_ledger_only',
      notice: 'Server-controlled statement notice.',
    },
  });

  assert.match(markup, /August 2026/);
  assert.match(markup, /Interest Income/);
  assert.match(markup, /Operating Expense/);
  assert.match(markup, /1,250\.00/);
  assert.match(markup, /875\.00/);
  assert.match(markup, /777\.00/);
  assert.match(markup, /4,321\.00/);
  assert.match(markup, /3,210\.00/);
  assert.match(markup, /Server-controlled statement notice\./);
  assert.doesNotMatch(markup, />60\.00</);
});

test('Management workspace mounts Financial Statements only through the isolated accounting.view integration', () => {
  assert.match(managementSource, /management-financial-statements\.js/);
  assert.match(managementSource, /hasPermission\(session, 'accounting\.view'\)/);
  assert.match(managementSource, /loadManagementFinancialStatements/);
  assert.match(managementSource, /financialStatementsMarkup/);
  assert.match(managementSource, /id="management-financial-statements"/);
});
