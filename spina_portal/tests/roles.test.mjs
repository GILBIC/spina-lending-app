import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  ROLE_ENDPOINTS,
  availableRoleActions,
  normalizeRole,
} from '../assets/roles.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';

const areaNode = {
  area_id: 'cardona',
  parent_area_id: null,
  name: 'Cardona',
  full_path: 'Cardona',
  depth: 0,
  sort_order: 0,
  is_active: true,
  is_legacy_unmapped: false,
  explicit_collector: null,
  effective_collector: null,
  effective_collector_source_area_id: null,
  direct_client_count: 0,
  subtree_client_count: 0,
  child_count: 0,
};

function areaRoot() {
  return {
    innerHTML: '',
    addEventListener() {},
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
}

function workspaceRoot(areaSelector) {
  const mountedAreaRoot = areaRoot();
  return {
    areaRoot: mountedAreaRoot,
    root: {
      innerHTML: '',
      addEventListener() {},
      querySelector(selector) {
        return selector === areaSelector ? mountedAreaRoot : null;
      },
      querySelectorAll() {
        return [];
      },
    },
  };
}

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

test('Employee mounts shared Area Management only when an Area permission is present', async () => {
  const calls = [];
  const navigation = [];
  const { root, areaRoot: mountedAreaRoot } = workspaceRoot('#employee-area-management');
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') return { profile: { full_name: 'Office Staff' } };
      if (path === '/api/v1/activity-notifications') return [];
      if (path === '/api/v1/areas') return { areas: [areaNode] };
      throw new Error(`Unexpected Employee request: ${path}`);
    },
  };

  await mountEmployeeWorkspace({
    api,
    root,
    session: { permissions: ['area.manage'] },
    setNavigation(items) {
      navigation.push(...items);
    },
  });

  assert.ok(navigation.some((item) => item.label === 'Area Management'));
  assert.ok(calls.includes('/api/v1/areas'));
  assert.match(mountedAreaRoot.innerHTML, /AREA MANAGEMENT/i);
  assert.equal(mountedAreaRoot.innerHTML.includes('Retire'), false);
});

test('Employee with unrelated permissions does not expose or load Area Management', async () => {
  const calls = [];
  const navigation = [];
  const { root } = workspaceRoot('#employee-area-management');
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') return { profile: { full_name: 'Office Staff' } };
      if (path === '/api/v1/activity-notifications') return [];
      throw new Error(`Unexpected Employee request: ${path}`);
    },
  };

  await mountEmployeeWorkspace({
    api,
    root,
    session: { permissions: [] },
    setNavigation(items) {
      navigation.push(...items);
    },
  });

  assert.equal(navigation.some((item) => item.label === 'Area Management'), false);
  assert.equal(calls.some((path) => path.startsWith('/api/v1/areas')), false);
});

test('Management mounts the same shared Area component and receives retirement controls', async () => {
  const calls = [];
  const navigation = [];
  const { root, areaRoot: mountedAreaRoot } = workspaceRoot('#management-area-management');
  const api = {
    async request(path) {
      calls.push(path);
      if (path === '/api/v1/account') return { profile: { full_name: 'Management' } };
      if (path === '/api/v1/management/loans?status=active') return { summary: {}, loans: [] };
      if (path === '/api/v1/areas?include_inactive=true') return { areas: [areaNode] };
      throw new Error(`Unexpected Management request: ${path}`);
    },
  };

  await mountManagementWorkspace({
    api,
    root,
    session: { permissions: ['area.retire'] },
    setNavigation(items) {
      navigation.push(...items);
    },
  });

  assert.ok(navigation.some((item) => item.label === 'Area Management'));
  assert.ok(calls.includes('/api/v1/areas?include_inactive=true'));
  assert.match(mountedAreaRoot.innerHTML, /AREA MANAGEMENT/i);
  assert.match(mountedAreaRoot.innerHTML, />Retire Area<\/button>/);
});

test('role workspaces never duplicate Area API implementation outside the shared module', () => {
  for (const relativePath of [
    '../assets/roles/employee.js',
    '../assets/roles/management.js',
  ]) {
    const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
    assert.equal(source.includes('/api/v1/areas'), false, `${relativePath} must delegate Area API work`);
  }
});
