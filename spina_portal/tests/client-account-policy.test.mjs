import assert from 'node:assert/strict';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';

test('Management Client invitation is exposed only with account.manage', () => {
  const withoutAccountManage = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const withAccountManage = availableRoleActions('management', [
    'account.manage',
  ]);

  assert.equal(
    withoutAccountManage.some(
      (entry) => entry.path === '/api/v1/management/client-accounts/invite',
    ),
    false,
  );
  assert.ok(
    withAccountManage.some(
      (entry) =>
        entry.path === '/api/v1/management/client-accounts/invite' &&
        entry.permission === 'account.manage',
    ),
  );
});
