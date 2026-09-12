import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

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
