import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

test('Management Past-Due Reason Reporting requires management.dashboard.view and stays read-only', () => {
  const withoutDashboard = availableRoleActions('management', ['accounting.view']);
  const withDashboard = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const employee = availableRoleActions('employee', [
    'management.dashboard.view',
  ]);
  const collector = availableRoleActions('collector', [
    'management.dashboard.view',
  ]);

  assert.equal(
    withoutDashboard.some((entry) => entry.key === 'management-past-due-report'),
    false,
  );

  const action = withDashboard.find(
    (entry) => entry.key === 'management-past-due-report',
  );

  assert.ok(action);
  assert.equal(action.path, '/api/v1/management/past-due/reasons');
  assert.equal(action.permission, 'management.dashboard.view');
  assert.equal(Object.hasOwn(action, 'method'), false);
  assert.equal(Object.hasOwn(action, 'financial'), false);

  assert.equal(
    employee.some((entry) => entry.path.includes('/management/past-due/')),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path.includes('/management/past-due/')),
    false,
  );
});
