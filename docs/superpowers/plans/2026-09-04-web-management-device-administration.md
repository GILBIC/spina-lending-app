# Web Management Device Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Web Management `Staff & devices` surface to functional parity for Collector phone administration so an authorized Management user can inspect registered phones and approve, revoke, or restore them from the browser.

**Architecture:** Keep the existing FastAPI management device endpoints as the server authority. Add a small browser module for deterministic device presentation and API calls, then integrate it into `management.js` with a staff-row `Manage` action and a detail region. Every mutation remains permission-gated by `device.manage`, requires an explicit confirmation, and refreshes from the server after completion.

**Tech Stack:** Vanilla ES modules, Node.js `node:test`, existing `SpinaApi`, FastAPI management API.

**Spec:** `docs/superpowers/specs/2026-08-28-ca2-staff-device-administration-design.md`

## Global Constraints

- Preserve server-authoritative permissions; browser UI never grants authority.
- Device detail and mutations require `device.manage`.
- Pending Collector mobile devices can become `active` only after explicit Management approval.
- `active` devices can be changed to `revoked`; `revoked` devices can be restored to `active`.
- Approving a pending Collector phone must warn that another active Collector phone may be revoked by the server policy.
- Do not expose raw device identifiers or hashes.
- Do not change lending, collection, accounting, authentication, or database rules.

---

### Task 1: Device administration browser contract

**Files:**
- Create: `spina_portal/assets/management-devices.js`
- Create: `spina_portal/tests/management-devices.test.mjs`

**Interfaces:**
- Consumes: `SpinaApi.request(path, options)` and plain staff/device payloads returned by the existing management API.
- Produces: `deviceAction(status)`, `loadManagedDevices(api, userId)`, `changeManagedDeviceStatus(api, deviceId, status)`, and `renderManagedDevicePanel(account, devices, options)`.

- [ ] **Step 1: Write the failing tests**

```js
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  changeManagedDeviceStatus,
  deviceAction,
  loadManagedDevices,
  renderManagedDevicePanel,
} from '../assets/management-devices.js';

test('pending phones map to the explicit approve action', () => {
  assert.deepEqual(deviceAction('pending'), { nextStatus: 'active', label: 'Approve phone' });
});

test('device detail uses the existing Management device endpoints', async () => {
  const calls = [];
  const api = { request: async (path, options = {}) => { calls.push([path, options]); return { devices: [] }; } };
  await loadManagedDevices(api, 'staff-1');
  await changeManagedDeviceStatus(api, 'device-1', 'active');
  assert.equal(calls[0][0], '/api/v1/management/accounts/staff-1/devices');
  assert.deepEqual(calls[1], ['/api/v1/management/devices/device-1/status', { method: 'PATCH', body: { status: 'active' } }]);
});

test('pending Collector phone renders approval warning without exposing identifiers', () => {
  const html = renderManagedDevicePanel(
    { id: 'staff-1', full_name: 'Collector One', username: 'collector.one', roles: ['collector'] },
    [{ id: 'device-secret', platform: 'android', app_version: '0.1.0', status: 'pending', registered_at: '2026-09-04T00:00:00Z', last_seen_at: null }],
    { canManageDevices: true },
  );
  assert.match(html, /Approve phone/);
  assert.match(html, /another active Collector phone/i);
  assert.doesNotMatch(html, /device-secret/);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `node --test spina_portal/tests/management-devices.test.mjs`

Expected: FAIL because `../assets/management-devices.js` does not exist.

- [ ] **Step 3: Implement the minimal device administration module**

Implement the four exported functions. URL-encode all path identifiers. Render only platform, app version, status, registered timestamp, and last-seen timestamp. Put the managed device ID only in an internal `data-managed-device-id` attribute used by the action handler; do not render it as visible text.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `node --test spina_portal/tests/management-devices.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/management-devices.js spina_portal/tests/management-devices.test.mjs
git commit -m "feat: add web management device contract"
```

### Task 2: Management Staff & devices drill-down

**Files:**
- Modify: `spina_portal/assets/roles/management.js`
- Modify: `spina_portal/tests/management-devices.test.mjs`

**Interfaces:**
- Consumes: Task 1 exports and existing `hasPermission`, `setButtonBusy`, `showToast`, `errorCard`, `escapeHtml` helpers.
- Produces: staff `Manage` buttons, `#management-staff-device-detail` detail region, and browser event handlers for device status changes.

- [ ] **Step 1: Add failing integration-contract assertions**

Add source-level assertions that `management.js` imports the Task 1 module, renders `data-manage-staff-id`, renders `management-staff-device-detail`, checks `device.manage`, and binds `.managed-device-action` controls.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `node --test spina_portal/tests/management-devices.test.mjs`

Expected: FAIL because the current Management web page only renders a staff table and has no device drill-down.

- [ ] **Step 3: Implement the minimal browser integration**

Update the staff table with a `Manage` button per row. On click, load `/api/v1/management/accounts/{user_id}/devices`; render the selected staff account and devices into `#management-staff-device-detail`. Show read-only device detail when the session lacks `device.manage`. When permitted, bind `Approve phone`, `Revoke phone`, and `Restore phone` buttons. Before mutation, show an explicit confirmation describing current status, requested status, and consequence. After success, reload the authoritative device list and show a success toast. On failure, render/toast the server error without assuming the state changed.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `node --test spina_portal/tests/management-devices.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/roles/management.js spina_portal/tests/management-devices.test.mjs
git commit -m "feat: manage staff devices from web"
```

### Task 3: Endpoint catalog parity

**Files:**
- Modify: `spina_portal/assets/roles.js`
- Modify: `spina_portal/tests/roles.test.mjs`

**Interfaces:**
- Consumes: existing `ROLE_ENDPOINTS` and `availableRoleActions`.
- Produces: explicit Management staff/device endpoint catalog entries guarded by `device.manage`.

- [ ] **Step 1: Write the failing role-catalog test**

```js
test('Management device administration is exposed only with device.manage', () => {
  const without = availableRoleActions('management', ['account.manage']);
  const withDevice = availableRoleActions('management', ['device.manage']);
  assert.equal(without.some((entry) => entry.key === 'management-staff-devices'), false);
  assert.ok(withDevice.some((entry) => entry.key === 'management-staff-devices'));
});
```

- [ ] **Step 2: Run the role test and verify RED**

Run: `node --test spina_portal/tests/roles.test.mjs`

Expected: FAIL because the Management catalog does not yet include staff device administration.

- [ ] **Step 3: Add the catalog entry**

Add an entry for `/api/v1/management/accounts` labeled `Staff & devices` with `permission: 'device.manage'`. Keep parameterized device-detail and mutation paths in the dedicated device module rather than inventing fake literal IDs in `ROLE_ENDPOINTS`.

- [ ] **Step 4: Run the role test and verify GREEN**

Run: `node --test spina_portal/tests/roles.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/roles.js spina_portal/tests/roles.test.mjs
git commit -m "test: cover web device administration permission"
```

### Task 4: Full portal verification and PR gate

**Files:**
- No production files beyond Tasks 1-3.

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: a reviewable PR with exact-head CI evidence.

- [ ] **Step 1: Run all portal tests**

Run: `npm test`

Expected: all portal tests PASS.

- [ ] **Step 2: Build the public portal**

Run: `node tools/build_portal.mjs`

Expected: exit 0 and `dist/index.html`, `dist/assets/app.js`, plus the new device module included in the public build.

- [ ] **Step 3: Verify no forbidden backend secret patterns**

Run: `grep -R -E "GILBIC_(DATABASE_URL|SUPABASE_SECRET_KEY)|service_role|postgresql://" dist && exit 1 || exit 0`

Expected: exit 0 with no matches.

- [ ] **Step 4: Open PR and require exact-head SPINA CI**

PR title: `Add Web Management device approval`

Expected CI lanes: Backend, quality, and security; Portal, Flutter, and Android; Financial and disposable PostgreSQL — all success before merge.

- [ ] **Step 5: Production acceptance after deployment**

Sign in as an authorized Management user on Web, open `Staff & devices`, select the pending Collector account, approve the pending Android phone, then retry Collector mobile sign-in. Acceptance requires the Collector phone to authenticate successfully and the device to read `active` on a fresh Management reload.
