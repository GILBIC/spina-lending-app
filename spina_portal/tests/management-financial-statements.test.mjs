import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

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
