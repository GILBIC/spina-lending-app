import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildAreaTree,
  mountAreaManagement,
  renderAreaManagementShell,
} from '../assets/area-management.js';

const activeArea = {
  area_id: 'calahan',
  parent_area_id: null,
  name: 'Calahan',
  full_path: 'Calahan',
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

const inactiveArea = {
  ...activeArea,
  is_active: false,
};

const clearPreview = {
  area_id: 'calahan',
  full_path: 'Calahan',
  is_active: true,
  active_direct_client_count: 0,
  active_subtree_client_count: 0,
  active_collector_assignment_count: 0,
  pending_transfer_target_count: 0,
  descendant_count: 0,
  active_descendant_count: 0,
};

const blockedPreview = {
  ...clearPreview,
  active_direct_client_count: 1,
  active_subtree_client_count: 2,
  active_collector_assignment_count: 1,
  pending_transfer_target_count: 1,
};

function interactiveRoot() {
  const listeners = new Map();
  return {
    innerHTML: '',
    addEventListener(type, handler) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    async dispatch(type, target) {
      for (const handler of listeners.get(type) || []) {
        await handler({ target, preventDefault() {} });
      }
    },
  };
}

function areaActionTarget(action) {
  const button = {
    dataset: { areaAction: action },
    closest(selector) {
      if (selector === '[data-area-action]') return button;
      return null;
    },
  };
  return button;
}

function retirementConfirmTarget() {
  const button = {
    closest(selector) {
      if (selector === '[data-area-retirement-confirm]') return button;
      return null;
    },
  };
  return button;
}

function retirementApi({ preview = clearPreview, initiallyActive = true } = {}) {
  const calls = [];
  let isActive = initiallyActive;
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if ((path === '/api/v1/areas' || path === '/api/v1/areas?include_inactive=true') && !options.method) {
        return { areas: [{ ...(isActive ? activeArea : inactiveArea) }] };
      }
      if (path === '/api/v1/areas/calahan/retirement-preview' && !options.method) {
        return preview;
      }
      if (path === '/api/v1/areas/calahan/retire' && options.method === 'POST') {
        isActive = false;
        return { area_id: 'calahan' };
      }
      if (path === '/api/v1/areas/calahan/reactivate' && options.method === 'POST') {
        isActive = true;
        return { area_id: 'calahan' };
      }
      throw new Error(`Unexpected Area retirement request: ${path}`);
    },
  };
  return { api, calls };
}

test('retirement lifecycle controls require exact area.retire and never expose hard Delete', () => {
  const tree = buildAreaTree([activeArea]);
  const employeeHtml = renderAreaManagementShell({
    tree,
    selectedAreaId: 'calahan',
    session: { permissions: ['area.manage', 'area.collector.assign', 'area.client.assign'] },
  });
  assert.doesNotMatch(employeeHtml, /Retire Area|Reactivate Area/i);
  assert.doesNotMatch(employeeHtml, /Delete Area/i);

  const managementHtml = renderAreaManagementShell({
    tree,
    selectedAreaId: 'calahan',
    session: { permissions: ['area.retire'] },
  });
  assert.match(managementHtml, /Retire Area/i);
  assert.doesNotMatch(managementHtml, /Delete Area/i);
});

test('blocked retirement preview shows authoritative dependencies and never submits retirement', async () => {
  const { api, calls } = retirementApi({ preview: blockedPreview });
  const root = interactiveRoot();

  await mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.retire'] },
  });
  await root.dispatch('click', areaActionTarget('retire'));

  assert.equal(
    calls.some((call) => call.path === '/api/v1/areas/calahan/retirement-preview'),
    true,
  );
  assert.match(root.innerHTML, /2 active Clients/i);
  assert.match(root.innerHTML, /1 active Collector assignment/i);
  assert.match(root.innerHTML, /1 pending transfer/i);
  assert.equal(root.innerHTML.includes('data-area-retirement-confirm'), false);
  assert.equal(
    calls.some((call) => call.path === '/api/v1/areas/calahan/retire' && call.options.method === 'POST'),
    false,
  );
});

test('dependency-free Area retires only after explicit confirmation and remains visible as inactive', async () => {
  const { api, calls } = retirementApi({ preview: clearPreview });
  const root = interactiveRoot();

  await mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.retire'] },
  });
  await root.dispatch('click', areaActionTarget('retire'));

  assert.match(root.innerHTML, /Retire Area/i);
  assert.match(root.innerHTML, /data-area-retirement-confirm/);
  assert.equal(
    calls.some((call) => call.path === '/api/v1/areas/calahan/retire' && call.options.method === 'POST'),
    false,
  );

  await root.dispatch('click', retirementConfirmTarget());

  const retires = calls.filter(
    (call) => call.path === '/api/v1/areas/calahan/retire' && call.options.method === 'POST',
  );
  assert.equal(retires.length, 1);
  assert.match(root.innerHTML, /inactive/i);
  assert.match(root.innerHTML, /Reactivate Area/i);
  assert.doesNotMatch(root.innerHTML, /Delete Area/i);
});

test('inactive Area can be reactivated through exact protected action and authoritative reload', async () => {
  const { api, calls } = retirementApi({ initiallyActive: false });
  const root = interactiveRoot();

  await mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.retire'] },
  });
  assert.match(root.innerHTML, /Reactivate Area/i);

  await root.dispatch('click', areaActionTarget('reactivate'));

  const reactivates = calls.filter(
    (call) => call.path === '/api/v1/areas/calahan/reactivate' && call.options.method === 'POST',
  );
  assert.equal(reactivates.length, 1);
  assert.match(root.innerHTML, /active/i);
  assert.match(root.innerHTML, /Retire Area/i);
});
