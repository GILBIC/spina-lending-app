import assert from 'node:assert/strict';
import test from 'node:test';

import * as areaManagementModule from '../assets/area-management.js';
import { buildAreaTree, renderAreaManagementShell } from '../assets/area-management.js';

const collectorA = {
  user_id: 'collector-a',
  username: 'collector.a',
  full_name: 'Collector A',
};

const collectorB = {
  user_id: 'collector-b',
  username: 'collector.b',
  full_name: 'Collector B',
};

const inheritedNiaNodes = [
  {
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
    subtree_client_count: 8,
    child_count: 1,
  },
  {
    area_id: 'calahan',
    parent_area_id: 'cardona',
    name: 'Calahan',
    full_path: 'Cardona › Calahan',
    depth: 1,
    sort_order: 0,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: collectorA,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'calahan',
    direct_client_count: 1,
    subtree_client_count: 8,
    child_count: 2,
  },
  {
    area_id: 'balayong',
    parent_area_id: 'calahan',
    name: 'Balayong',
    full_path: 'Cardona › Calahan › Balayong',
    depth: 2,
    sort_order: 0,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'calahan',
    direct_client_count: 3,
    subtree_client_count: 3,
    child_count: 0,
  },
  {
    area_id: 'nia',
    parent_area_id: 'calahan',
    name: 'NIA',
    full_path: 'Cardona › Calahan › NIA',
    depth: 2,
    sort_order: 1,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'calahan',
    direct_client_count: 4,
    subtree_client_count: 4,
    child_count: 0,
  },
];

const explicitNiaNodes = inheritedNiaNodes.map((node) =>
  node.area_id === 'nia'
    ? {
        ...node,
        explicit_collector: collectorB,
        effective_collector: collectorB,
        effective_collector_source_area_id: 'nia',
      }
    : node,
);

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

function areaRowTarget(areaId) {
  const row = {
    dataset: { areaId },
    closest(selector) {
      if (selector === '[data-area-id]') return row;
      return null;
    },
  };
  return row;
}

function collectorSelectTarget(collectorUserId) {
  return {
    value: collectorUserId,
    matches(selector) {
      return selector === '[data-area-collector-select]';
    },
  };
}

function collectorEditorTarget(collectorUserId) {
  return {
    elements: { collector_user_id: { value: collectorUserId } },
    matches(selector) {
      return selector === '[data-area-collector-editor]';
    },
  };
}

function collectorRemoveTarget() {
  const button = {
    closest(selector) {
      if (selector === '[data-area-collector-remove]') return button;
      return null;
    },
  };
  return button;
}

function collectorApi({ initialNodes, refreshedNodes = initialNodes, conflictOnPut = false }) {
  const calls = [];
  let areaReadCount = 0;
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) {
        areaReadCount += 1;
        return { areas: areaReadCount === 1 ? initialNodes : refreshedNodes };
      }
      if (path === '/api/v1/areas/collectors' && !options.method) {
        return { collectors: [collectorA, collectorB] };
      }
      if (path === '/api/v1/areas/nia/collector' && options.method === 'PUT') {
        if (conflictOnPut) {
          const error = new Error('authoritative collector ownership conflict');
          error.status = 409;
          throw error;
        }
        return { assignment_id: 'assignment-b' };
      }
      if (path === '/api/v1/areas/nia/collector' && options.method === 'DELETE') {
        return { collector_user_id: 'collector-b' };
      }
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  return { api, calls, getAreaReadCount: () => areaReadCount };
}

test('Collector ownership details distinguish explicit, inherited, and unassigned server states', () => {
  const inheritedHtml = renderAreaManagementShell({
    tree: buildAreaTree(inheritedNiaNodes),
    selectedAreaId: 'nia',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    session: { permissions: ['area.collector.assign'] },
  });
  assert.match(inheritedHtml, /Inherited:\s*Collector A from Calahan/i);

  const explicitHtml = renderAreaManagementShell({
    tree: buildAreaTree(explicitNiaNodes),
    selectedAreaId: 'nia',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    session: { permissions: ['area.collector.assign'] },
  });
  assert.match(explicitHtml, /Explicit:\s*Collector B/i);

  const unassignedHtml = renderAreaManagementShell({
    tree: buildAreaTree(inheritedNiaNodes),
    selectedAreaId: 'cardona',
    expandedAreaIds: new Set(['cardona']),
    session: { permissions: ['area.collector.assign'] },
  });
  assert.match(unassignedHtml, /Unassigned/i);
});

test('Collector action works with area.collector.assign alone and shows active server Collector choices', async () => {
  const { api } = collectorApi({ initialNodes: inheritedNiaNodes });
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));
  await root.dispatch('click', areaActionTarget('collector'));

  assert.match(root.innerHTML, /data-area-collector-editor/);
  assert.match(root.innerHTML, /Collector A/);
  assert.match(root.innerHTML, /Collector B/);
  assert.match(root.innerHTML, /value="collector-a"/);
  assert.match(root.innerHTML, /value="collector-b"/);
});

test('Collector selection explains inherited descendant handling before save', async () => {
  const { api } = collectorApi({ initialNodes: inheritedNiaNodes });
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));
  await root.dispatch('click', areaActionTarget('collector'));
  await root.dispatch('change', collectorSelectTarget('collector-b'));

  assert.match(
    root.innerHTML,
    /Collector B will handle NIA and its descendants unless a deeper Subarea has its own Collector override\./,
  );
});

test('assigning NIA to Collector B PUTs only the exact override and reloads authoritative ownership', async () => {
  const { api, calls, getAreaReadCount } = collectorApi({
    initialNodes: inheritedNiaNodes,
    refreshedNodes: explicitNiaNodes,
  });
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));
  await root.dispatch('click', areaActionTarget('collector'));
  await root.dispatch('change', collectorSelectTarget('collector-b'));
  await root.dispatch('submit', collectorEditorTarget('collector-b'));

  const collectorWrites = calls.filter((call) => call.options.method === 'PUT');
  assert.equal(collectorWrites.length, 1, 'assignment must not enumerate or mutate descendant Areas');
  assert.equal(collectorWrites[0].path, '/api/v1/areas/nia/collector');
  assert.deepEqual(collectorWrites[0].options.body, { collector_user_id: 'collector-b' });
  assert.equal(getAreaReadCount(), 2, 'successful assignment must reload the authoritative Area tree');
  assert.match(root.innerHTML, /Explicit:\s*Collector B/i);

  await root.dispatch('click', areaRowTarget('calahan'));
  assert.match(root.innerHTML, /Explicit:\s*Collector A/i);
});

test('removing the NIA exact override DELETEs only NIA and reloads inherited Collector A', async () => {
  const { api, calls, getAreaReadCount } = collectorApi({
    initialNodes: explicitNiaNodes,
    refreshedNodes: inheritedNiaNodes,
  });
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));
  await root.dispatch('click', areaActionTarget('collector'));
  await root.dispatch('click', collectorRemoveTarget());

  const collectorDeletes = calls.filter((call) => call.options.method === 'DELETE');
  assert.equal(collectorDeletes.length, 1, 'removal must touch only the exact NIA override');
  assert.equal(collectorDeletes[0].path, '/api/v1/areas/nia/collector');
  assert.equal(getAreaReadCount(), 2, 'successful removal must reload the authoritative Area tree');
  assert.match(root.innerHTML, /Inherited:\s*Collector A from Calahan/i);

  await root.dispatch('click', areaRowTarget('calahan'));
  assert.match(root.innerHTML, /Explicit:\s*Collector A/i);
});

test('Collector assignment 409 fails closed, preserves prior ownership, and asks for Staff review', async () => {
  const { api } = collectorApi({
    initialNodes: inheritedNiaNodes,
    conflictOnPut: true,
  });
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));
  await root.dispatch('click', areaActionTarget('collector'));
  await root.dispatch('change', collectorSelectTarget('collector-b'));
  await root.dispatch('submit', collectorEditorTarget('collector-b'));

  assert.match(root.innerHTML, /Conflict — SPINA requires Staff review/i);
  assert.match(root.innerHTML, /Inherited:\s*Collector A from Calahan/i);
});

test('Collector assignment controls remain absent without area.collector.assign', async () => {
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas') return { areas: inheritedNiaNodes };
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaRowTarget('nia'));

  assert.equal(root.innerHTML.includes('data-area-action="collector"'), false);
  assert.equal(calls.some((call) => call.path === '/api/v1/areas/collectors'), false);
  assert.equal(calls.some((call) => call.options.method === 'PUT' || call.options.method === 'DELETE'), false);
});
