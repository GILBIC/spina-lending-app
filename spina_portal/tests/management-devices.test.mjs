import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  changeManagedDeviceStatus,
  deviceAction,
  loadManagedDevices,
  renderManagedDevicePanel,
} from '../assets/management-devices.js';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);

test('pending phones map to the explicit approve action', () => {
  assert.deepEqual(deviceAction('pending'), {
    nextStatus: 'active',
    label: 'Approve phone',
  });
  assert.deepEqual(deviceAction('active'), {
    nextStatus: 'revoked',
    label: 'Revoke phone',
  });
  assert.deepEqual(deviceAction('revoked'), {
    nextStatus: 'active',
    label: 'Restore phone',
  });
});

test('device detail uses the existing Management device endpoints', async () => {
  const calls = [];
  const api = {
    request: async (path, options = {}) => {
      calls.push([path, options]);
      return { devices: [] };
    },
  };

  await loadManagedDevices(api, 'staff / one');
  await changeManagedDeviceStatus(api, 'device / one', 'active');

  assert.equal(
    calls[0][0],
    '/api/v1/management/accounts/staff%20%2F%20one/devices',
  );
  assert.deepEqual(calls[1], [
    '/api/v1/management/devices/device%20%2F%20one/status',
    { method: 'PATCH', body: { status: 'active' } },
  ]);
});

test('pending Collector phone renders approval warning without showing its raw identifier', () => {
  const html = renderManagedDevicePanel(
    {
      id: 'staff-1',
      full_name: 'Collector One',
      username: 'collector.one',
      roles: ['collector'],
    },
    [
      {
        id: 'device-secret',
        platform: 'android',
        app_version: '0.1.0',
        status: 'pending',
        registered_at: '2026-09-04T00:00:00Z',
        last_seen_at: null,
      },
    ],
    { canManageDevices: true },
  );

  assert.match(html, /Approve phone/);
  assert.match(html, /another active Collector phone/i);
  assert.match(html, /data-managed-device-index="0"/);
  assert.doesNotMatch(html, /device-secret/);
});

test('device actions are omitted without device.manage', () => {
  const html = renderManagedDevicePanel(
    { id: 'staff-1', full_name: 'Employee One', username: 'employee.one', roles: ['employee'] },
    [
      {
        id: 'device-secret',
        platform: 'android',
        app_version: '0.1.0',
        status: 'active',
        registered_at: '2026-09-04T00:00:00Z',
        last_seen_at: '2026-09-04T01:00:00Z',
      },
    ],
    { canManageDevices: false },
  );

  assert.doesNotMatch(html, /managed-device-action/);
  assert.match(html, /device management permission/i);
});

test('Management web workspace exposes staff drill-down and device action binding', () => {
  assert.match(managementSource, /management-devices\.js/);
  assert.match(managementSource, /data-manage-staff-id/);
  assert.match(managementSource, /management-staff-device-detail/);
  assert.match(managementSource, /device\.manage/);
  assert.match(managementSource, /managed-device-action/);
});
