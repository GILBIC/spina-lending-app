import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

test('Management Loan Operations stays Management-only without inventing a Web permission', () => {
  const management = availableRoleActions('management', []);
  const employee = availableRoleActions('employee', []);
  const collector = availableRoleActions('collector', []);

  const action = management.find((entry) => entry.key === 'management-loan-operations');

  assert.ok(action);
  assert.equal(action.path, '/api/v1/management/loan-operations');
  assert.equal(action.section, 'Operations');
  assert.equal(Object.hasOwn(action, 'permission'), false);
  assert.equal(
    employee.some((entry) => entry.path === '/api/v1/management/loan-operations'),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path === '/api/v1/management/loan-operations'),
    false,
  );
});
