import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  bindManagedDevicePanel,
  deviceAction,
  renderManagedDevicePanel,
} from '../assets/management-devices.js';
import { Element, fire } from './helpers/dom.mjs';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);

const account = {
  id: 'staff-1',
  full_name: 'SPINA REVIEW EMPLOYEE (TEST ONLY)',
  username: 'spina_review_employee_0921',
  roles: ['employee'],
};

const devices = [
  {
    id: 'device-active-web',
    platform: 'web',
    app_version: '0.1.0',
    status: 'active',
    registered_at: '2026-09-22T11:20:00+08:00',
    last_seen_at: '2026-09-22T11:24:00+08:00',
  },
  {
    id: 'device-pending-android',
    platform: 'android',
    app_version: '0.4.0+4',
    status: 'pending',
    registered_at: '2026-09-22T13:24:00+08:00',
    last_seen_at: null,
  },
  {
    id: 'device-revoked-desktop',
    platform: 'desktop',
    app_version: '0.4.0',
    status: 'revoked',
    registered_at: '2026-09-21T15:25:00+08:00',
    last_seen_at: '2026-09-21T15:25:00+08:00',
  },
  {
    id: 'device-active-ios',
    platform: 'ios',
    app_version: '0.4.0',
    status: 'active',
    registered_at: '2026-09-20T08:00:00+08:00',
    last_seen_at: '2026-09-20T08:30:00+08:00',
  },
];

test('device actions use platform-neutral access wording', () => {
  assert.deepEqual(deviceAction('pending'), {
    nextStatus: 'active',
    label: 'Approve device',
  });
  assert.deepEqual(deviceAction('active'), {
    nextStatus: 'revoked',
    label: 'Revoke access',
  });
  assert.deepEqual(deviceAction('revoked'), {
    nextStatus: 'active',
    label: 'Restore access',
  });
});

test('selected staff panel shows exact device counts and compact filters without raw IDs', () => {
  const html = renderManagedDevicePanel(account, devices, {
    canManageDevices: true,
  });

  assert.match(html, /4 devices/);
  assert.match(html, /2 active/);
  assert.match(html, /1 pending/);
  assert.match(html, /1 revoked/);

  for (const filter of ['all', 'active', 'pending', 'revoked']) {
    assert.match(
      html,
      new RegExp(`data-managed-device-filter="${filter}"`),
    );
  }

  for (const status of ['active', 'pending', 'revoked']) {
    assert.match(
      html,
      new RegExp(`data-managed-device-status="${status}"`),
    );
  }

  assert.match(html, /Web/);
  assert.match(html, /Android/);
  assert.match(html, /Desktop/);
  assert.match(html, /iOS/);
  assert.match(html, /Employee/);
  assert.doesNotMatch(html, /device-active-web|device-pending-android|device-revoked-desktop/);
});

test('device cards keep facts but do not repeat mutation consequences', () => {
  const html = renderManagedDevicePanel(account, devices, {
    canManageDevices: true,
  });

  assert.match(html, /App version 0\.1\.0/);
  assert.match(html, /Registered/);
  assert.match(html, /Last seen/);
  assert.doesNotMatch(
    html,
    /Revoking this phone blocks future protected requests/i,
  );
  assert.doesNotMatch(
    html,
    /Approving this phone allows protected SPINA access/i,
  );

  assert.match(
    html,
    /class="button button-danger managed-device-action"[^>]*>Revoke access</,
  );
  assert.match(html, />Approve device</);
  assert.match(html, />Restore access</);
});

test('device status filters are local and never remove authoritative device records', () => {
  const root = new Element();
  root.innerHTML = renderManagedDevicePanel(account, devices, {
    canManageDevices: true,
  });

  const cleanup = bindManagedDevicePanel(root);
  const allCards = root.querySelectorAll('[data-managed-device-status]');
  assert.equal(allCards.length, 4);

  fire(root.querySelector('[data-managed-device-filter="pending"]'), 'click');

  const pending = root.querySelectorAll('[data-managed-device-status="pending"]');
  const active = root.querySelectorAll('[data-managed-device-status="active"]');
  const revoked = root.querySelectorAll('[data-managed-device-status="revoked"]');
  assert.equal(pending.every((item) => item.getAttribute('hidden') === null), true);
  assert.equal(active.every((item) => item.getAttribute('hidden') === ''), true);
  assert.equal(revoked.every((item) => item.getAttribute('hidden') === ''), true);
  assert.equal(allCards.length, 4, 'filtering must not delete device evidence');

  fire(root.querySelector('[data-managed-device-filter="all"]'), 'click');
  assert.equal(
    root.querySelectorAll('[data-managed-device-status]')
      .every((item) => item.getAttribute('hidden') === null),
    true,
  );

  cleanup();
});

test('selected staff panel exposes a Close control', () => {
  const root = new Element();
  root.innerHTML = renderManagedDevicePanel(account, devices, {
    canManageDevices: true,
  });
  assert.ok(root.querySelector('[data-managed-device-close]'));
  assert.match(root.querySelector('[data-managed-device-close]').textContent, /Close/i);
});

test('Management staff table uses device terminology, human roles, account timestamp label and selected-row hook', () => {
  assert.match(managementSource, /Manage devices/);
  assert.doesNotMatch(managementSource, /Manage phones/);
  assert.match(managementSource, /Account updated/);
  assert.match(managementSource, /data-staff-row-id/);
  assert.match(managementSource, /aria-selected/);
  assert.match(managementSource, /titleCase\(String\(role/);
  assert.match(managementSource, /data-managed-device-close/);
  assert.match(managementSource, /Invite staff and manage registered devices\./);
});

test('device confirmation remains authoritative and platform-neutral', () => {
  assert.match(
    managementSource,
    /Revoking this device blocks future protected requests from this device\./,
  );
  assert.match(
    managementSource,
    /Approving this device may revoke another active Collector device for this account\./,
  );
  assert.doesNotMatch(managementSource, /Revoking this phone blocks future/);
});
