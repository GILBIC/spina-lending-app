import assert from 'node:assert/strict';
import test from 'node:test';

import * as clientRole from '../assets/roles/client.js';

test('Client Web account exposes revoke only for a non-current active device', () => {
  assert.equal(typeof clientRole.clientAccountCard, 'function');

  const html = clientRole.clientAccountCard({
    profile: {
      full_name: 'Client One',
      username: 'client.one',
      email: 'client@example.com',
      status: 'active',
    },
    devices: [
      {
        id: 'device-current',
        platform: 'android',
        app_version: '1.0.0',
        status: 'active',
        is_current: true,
      },
      {
        id: 'device-old',
        platform: 'ios',
        app_version: '0.9.0',
        status: 'active',
        is_current: false,
      },
      {
        id: 'device-revoked',
        platform: 'web',
        app_version: '1.0.0',
        status: 'revoked',
        is_current: false,
      },
    ],
  });

  assert.match(html, /data-client-revoke-device="device-old"/);
  assert.doesNotMatch(html, /data-client-revoke-device="device-current"/);
  assert.doesNotMatch(html, /data-client-revoke-device="device-revoked"/);
});

test('Client Web device revocation requires confirmation before protected POST', async () => {
  assert.equal(typeof clientRole.requestClientDeviceRevocation, 'function');

  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { device: { id: 'device-old', status: 'revoked' } };
    },
  };

  const cancelled = await clientRole.requestClientDeviceRevocation({
    api,
    deviceId: 'device-old',
    confirmRevoke: () => false,
  });
  assert.equal(cancelled, false);
  assert.equal(calls.length, 0);

  const confirmed = await clientRole.requestClientDeviceRevocation({
    api,
    deviceId: 'device-old',
    confirmRevoke: () => true,
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/account/devices/device-old/revoke',
      options: { method: 'POST' },
    },
  ]);
});
