import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { bindStaffDevices } from '../assets/roles/management.js';

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

test('unknown device statuses remain in All with exact total and no invented action', () => {
  const root = new Element();
  root.innerHTML = renderManagedDevicePanel(account, [...devices, { id: 'unknown-device-private', platform: 'web', status: 'suspended' }], { canManageDevices: true });
  assert.match(root.textContent, /5 devices.*2 active.*1 pending.*1 revoked.*1 other/);
  const card = root.querySelector('[data-managed-device-status="suspended"]');
  assert.ok(card); assert.equal(card.querySelector('.managed-device-action'), null);
  assert.doesNotMatch(root.innerHTML, /unknown-device-private/);
  const cleanup = bindManagedDevicePanel(root);
  fire(root.querySelector('[data-managed-device-filter="pending"]'), 'click');
  assert.equal(card.getAttribute('hidden'), '');
  fire(root.querySelector('[data-managed-device-filter="all"]'), 'click');
  assert.equal(card.getAttribute('hidden'), null); cleanup();
  fire(root.querySelector('[data-managed-device-filter="pending"]'), 'click');
  assert.equal(card.getAttribute('hidden'), null, 'disposed filter handlers stay inert');
});

function staffHarness({ permissions = ['device.manage'], request } = {}) {
  const root = new Element();
  root.innerHTML = '<table><tbody><tr data-staff-row-id="staff-1" aria-selected="false"><td><button data-manage-staff-id="staff-1">Manage devices</button></td></tr><tr data-staff-row-id="staff-2" aria-selected="false"><td><button data-manage-staff-id="staff-2">Manage devices</button></td></tr></tbody></table><div id="management-staff-device-detail" hidden></div>';
  const context = { root, session: { user: { roles: ['management'] }, permissions }, api: { request } };
  const cleanup = bindStaffDevices(context, [account, { ...account, id: 'staff-2', full_name: 'Second staff member' }]);
  return { root, cleanup, detail: root.querySelector('#management-staff-device-detail') };
}

test('staff detail focuses its heading and Close returns to the exact opener', async()=>{
 const h=staffHarness({request:async()=>({devices})});
 const opener=h.root.querySelector('[data-manage-staff-id="staff-1"]');fire(opener,'click');await setImmediate();
 assert.equal(h.detail.querySelector('[data-managed-device-heading]').focused,true);
 fire(h.detail.querySelector('[data-managed-device-close]'),'click');assert.equal(opener.focused,true);h.cleanup();
});

test('staff selection keeps only the latest detail and Close clears selection and detached actions', async () => {
  let first; const requests = [];
  const h = staffHarness({ request(path, options) {
    requests.push({ path, options });
    return path.includes('/staff-1/') ? new Promise((resolve) => { first = resolve; }) : Promise.resolve({ devices });
  } });
  fire(h.root.querySelector('[data-manage-staff-id="staff-1"]'), 'click');
  fire(h.root.querySelector('[data-manage-staff-id="staff-2"]'), 'click'); await setImmediate();
  assert.match(h.detail.textContent, /Second staff member/);
  first({ devices: [] }); await setImmediate();
  assert.match(h.detail.textContent, /Second staff member/);
  assert.equal(h.root.querySelector('[data-staff-row-id="staff-1"]').getAttribute('aria-selected'), 'false');
  assert.equal(h.root.querySelector('[data-staff-row-id="staff-2"]').getAttribute('aria-selected'), 'true');
  const oldAction = h.detail.querySelector('.managed-device-action');
  fire(h.detail.querySelector('[data-managed-device-close]'), 'click'); fire(oldAction, 'click'); await setImmediate();
  assert.equal(h.detail.getAttribute('hidden'), '');
  assert.equal(h.root.querySelector('[data-staff-row-id="staff-2"]').getAttribute('aria-selected'), 'false');
  assert.equal(requests.length, 2); h.cleanup();
});

test('staff account-only inspection cannot fetch or mutate registered devices', async () => {
  let requests = 0;
  const h = staffHarness({ permissions: ['account.manage'], request() { requests += 1; } });
  fire(h.root.querySelector('[data-manage-staff-id="staff-1"]'), 'click'); await setImmediate();
  assert.match(h.detail.textContent, /Device management permission/);
  assert.equal(h.detail.querySelector('.managed-device-action'), null);
  assert.equal(requests, 0); h.cleanup();
});

test('failed initial device read retains Close and returns focus to the selected staff opener',async()=>{
  const h=staffHarness({request:async()=>{throw new Error('Read unavailable');}});
  const opener=h.root.querySelector('[data-manage-staff-id="staff-1"]');
  fire(opener,'click');await setImmediate();
  assert.match(h.detail.textContent,/Read unavailable/);
  const close=h.detail.querySelector('[data-managed-device-close]');
  assert.ok(close,'A failed read must still provide a way to close the panel');
  fire(close,'click');assert.equal(opener.focused,true);
  assert.equal(h.detail.getAttribute('hidden'),'');h.cleanup();
});

test('late staff read neither focuses nor scrolls when the user moved to another control',async t=>{
  const original=globalThis.document;let resolve;
  t.after(()=>{globalThis.document=original;});
  const h=staffHarness({request:()=>new Promise(done=>{resolve=done;})});t.after(h.cleanup);
  const opener=h.root.querySelector('[data-manage-staff-id="staff-1"]');
  const elsewhere=h.root.querySelector('[data-manage-staff-id="staff-2"]');
  globalThis.document={activeElement:opener};let scrolls=0;h.detail.scrollIntoView=()=>scrolls++;
  fire(opener,'click');globalThis.document.activeElement=elsewhere;
  resolve({devices});await setImmediate();
  assert.notEqual(h.detail.querySelector('[data-managed-device-heading]').focused,true);
  assert.equal(scrolls,0,'A late response must not pull the user away from their current control');
});

test('Close returns to staff heading if the original opener is no longer present',async()=>{
  const h=staffHarness({request:async()=>({devices})});
  const heading=new Element('h3',{'data-management-staff-heading':''});h.root.appendChild(heading);
  const opener=h.root.querySelector('[data-manage-staff-id="staff-1"]');
  fire(opener,'click');await setImmediate();opener.remove();
  fire(h.detail.querySelector('[data-managed-device-close]'),'click');
  assert.equal(heading.focused,true);h.cleanup();
});

test('device mutation requires the consequence confirmation and one authoritative reload', async (t) => {
  const previous = globalThis.confirm; let accepted = false; const confirmations = [];
  globalThis.confirm = (message) => { confirmations.push(message); return accepted; };
  t.after(() => { globalThis.confirm = previous; });
  const requests = []; let finish;
  const h = staffHarness({ request(path, options = {}) {
    requests.push({ path, options });
    if (options.method === 'PATCH') return new Promise((resolve) => { finish = resolve; });
    return Promise.resolve({ devices: [devices[0]] });
  } });
  fire(h.root.querySelector('[data-manage-staff-id="staff-1"]'), 'click'); await setImmediate();
  const action = h.detail.querySelector('.managed-device-action');
  fire(action, 'click'); assert.equal(requests.length, 1);
  accepted = true; fire(action, 'click'); fire(action, 'click');
  assert.equal(requests.filter((call) => call.options.method === 'PATCH').length, 1);
  assert.match(confirmations[0], /Revoking this device blocks future protected requests/);
  assert.deepEqual(requests[1], { path: '/api/v1/management/devices/device-active-web/status', options: { method: 'PATCH', body: { status: 'revoked' } } });
  finish({}); await setImmediate();
  assert.equal(requests.length, 3); assert.match(h.detail.textContent, /1 device/); h.cleanup();
});
