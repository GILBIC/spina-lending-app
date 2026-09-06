import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

test('Management Client Accounts action is exposed only with account.manage', () => {
  const withoutAccountManage = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const withAccountManage = availableRoleActions('management', [
    'account.manage',
  ]);

  assert.equal(
    withoutAccountManage.some(
      (entry) => entry.path === '/api/v1/management/client-accounts',
    ),
    false,
  );

  const clientAccounts = withAccountManage.find(
    (entry) => entry.path === '/api/v1/management/client-accounts',
  );
  assert.ok(clientAccounts);
  assert.equal(clientAccounts.key, 'management-client-accounts');
  assert.equal(clientAccounts.label, 'Client accounts');
  assert.equal(clientAccounts.permission, 'account.manage');
  assert.equal(clientAccounts.method, 'POST');
});

test('Management role actions retire active Client self-registration and invite routes', () => {
  const actions = availableRoleActions('management', [
    'account.manage',
    'client.registration.approve',
  ]);

  assert.equal(
    actions.some(
      (entry) => entry.path === '/api/v1/management/client-accounts/invite',
    ),
    false,
  );
  assert.equal(
    actions.some(
      (entry) => entry.path === '/api/v1/management/client-registrations',
    ),
    false,
  );
});
