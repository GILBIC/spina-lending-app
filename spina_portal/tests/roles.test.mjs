import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ROLE_ENDPOINTS,
  availableRoleActions,
  normalizeRole,
} from '../assets/roles.js';

test('role names normalize to the four canonical experiences', () => {
  assert.equal(normalizeRole('Management'), 'management');
  assert.equal(normalizeRole(' employee '), 'employee');
  assert.equal(normalizeRole('COLLECTOR'), 'collector');
  assert.equal(normalizeRole('Client'), 'client');
  assert.equal(normalizeRole('viewer'), 'unknown');
});

test('Client endpoint catalog stays inside self-service and account boundaries', () => {
  const paths = ROLE_ENDPOINTS.client.map((entry) => entry.path);

  assert.ok(paths.includes('/api/v1/client/loans'));
  assert.ok(paths.includes('/api/v1/client/payments'));
  assert.ok(paths.includes('/api/v1/client/renewals'));
  assert.ok(paths.includes('/api/v1/client/support'));
  assert.ok(paths.includes('/api/v1/client/gcash/config'));
  assert.ok(paths.includes('/api/v1/account'));
  assert.ok(paths.includes('/api/v1/activity-notifications'));
  assert.equal(paths.some((path) => path.includes('/management/')), false);
  assert.equal(paths.some((path) => path.includes('/collector/')), false);
});

test('Employee has useful account and activity work but no Collector or Management mutation path', () => {
  const permissions = ['remittance.view', 'support.manage'];
  const actions = availableRoleActions('Employee', permissions);
  const paths = actions.map((entry) => entry.path);

  assert.ok(paths.includes('/api/v1/account'));
  assert.ok(paths.includes('/api/v1/activity-notifications'));
  assert.ok(paths.includes('/api/v1/notifications'));
  assert.ok(paths.includes('/api/v1/management/support'));
  assert.equal(paths.includes('/api/v1/collector/collections'), false);
  assert.equal(paths.some((path) => path.includes('/financial-accounting')), false);
});

test('permission-gated Employee actions disappear when permission is absent', () => {
  const paths = availableRoleActions('employee', []).map((entry) => entry.path);

  assert.deepEqual(paths.sort(), [
    '/api/v1/account',
    '/api/v1/activity-notifications',
  ]);
});

test('Collector catalog contains route work but not Management approvals', () => {
  const paths = availableRoleActions('collector', ['route.view', 'collection.create']).map(
    (entry) => entry.path,
  );

  assert.ok(paths.includes('/api/v1/collector/routes/today'));
  assert.ok(paths.includes('/api/v1/collector/collections'));
  assert.equal(paths.some((path) => path.includes('/management/')), false);
});

test('Management catalog requires exact permissions for protected families', () => {
  const basic = availableRoleActions('management', ['management.dashboard.view']);
  const expanded = availableRoleActions('management', [
    'management.dashboard.view',
    'renewal.manage',
    'support.manage',
    'remittance.view',
    'account.manage',
  ]);

  assert.ok(basic.some((entry) => entry.path === '/api/v1/management/dashboard-overview'));
  assert.ok(basic.some((entry) => entry.path === '/api/v1/management/loans'));
  assert.equal(basic.some((entry) => entry.path === '/api/v1/management/renewals'), false);
  assert.equal(basic.some((entry) => entry.path === '/api/v1/management/support'), false);
  assert.ok(expanded.some((entry) => entry.path === '/api/v1/management/renewals'));
  assert.ok(expanded.some((entry) => entry.path === '/api/v1/management/support'));
  assert.ok(expanded.some((entry) => entry.path === '/api/v1/notifications'));
});

test('Management device administration is exposed only with device.manage', () => {
  const withoutDevice = availableRoleActions('management', ['account.manage']);
  const withDevice = availableRoleActions('management', ['device.manage']);

  assert.equal(
    withoutDevice.some((entry) => entry.key === 'management-staff-devices'),
    false,
  );
  assert.ok(
    withDevice.some(
      (entry) =>
        entry.key === 'management-staff-devices' &&
        entry.path === '/api/v1/management/accounts',
    ),
  );
});
