import assert from 'node:assert/strict';
import test from 'node:test';

import * as areaManagementModule from '../assets/area-management.js';

const collectorA = {
  user_id: 'collector-a',
  username: 'collector.a',
  full_name: 'Collector A',
};

const collectorC = {
  user_id: 'collector-c',
  username: 'collector.c',
  full_name: 'Collector C',
};

const moveNodes = [
  {
    area_id: 'cardona',
    parent_area_id: null,
    name: 'Cardona',
    full_path: 'Cardona',
    depth: 0,
    sort_order: 0,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: collectorA,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'cardona',
    direct_client_count: 1,
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
    explicit_collector: null,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'cardona',
    direct_client_count: 2,
    subtree_client_count: 7,
    child_count: 1,
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
    effective_collector_source_area_id: 'cardona',
    direct_client_count: 5,
    subtree_client_count: 5,
    child_count: 0,
  },
  {
    area_id: 'morong',
    parent_area_id: null,
    name: 'Morong',
    full_path: 'Morong',
    depth: 0,
    sort_order: 1,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: null,
    effective_collector_source_area_id: null,
    direct_client_count: 0,
    subtree_client_count: 0,
    child_count: 2,
  },
  {
    area_id: 'destination',
    parent_area_id: 'morong',
    name: 'Destination',
    full_path: 'Morong › Destination',
    depth: 1,
    sort_order: 0,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: collectorC,
    effective_collector: collectorC,
    effective_collector_source_area_id: 'destination',
    direct_client_count: 0,
    subtree_client_count: 0,
    child_count: 0,
  },
  {
    area_id: 'retired-destination',
    parent_area_id: 'morong',
    name: 'Retired Destination',
    full_path: 'Morong › Retired Destination',
    depth: 1,
    sort_order: 1,
    is_active: false,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: null,
    effective_collector_source_area_id: null,
    direct_client_count: 0,
    subtree_client_count: 0,
    child_count: 0,
  },
];

const movedNodes = moveNodes.map((node) => {
  if (node.area_id === 'calahan') {
    return {
      ...node,
      parent_area_id: 'destination',
      full_path: 'Morong › Destination › Calahan',
      depth: 2,
      effective_collector: collectorC,
      effective_collector_source_area_id: 'destination',
    };
  }
  if (node.area_id === 'balayong') {
    return {
      ...node,
      full_path: 'Morong › Destination › Calahan › Balayong',
      depth: 3,
      effective_collector: collectorC,
      effective_collector_source_area_id: 'destination',
    };
  }
  return node;
});

const movePreview = {
  area_id: 'calahan',
  old_parent_area_id: 'cardona',
  new_parent_area_id: 'destination',
  old_path: 'Cardona › Calahan',
  new_path: 'Morong › Destination › Calahan',
  affected_node_count: 5,
  clients_affected: 23,
  descendant_areas_affected: 4,
  effective_collector_before: collectorA,
  effective_collector_after: collectorC,
  stale_delegated_access_count: 1,
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

function moveParentSelectTarget(parentAreaId) {
  return {
    value: parentAreaId,
    matches(selector) {
      return selector === '[data-area-move-parent-select]';
    },
  };
}

function movePreviewFormTarget(parentAreaId) {
  return {
    elements: { new_parent_area_id: { value: parentAreaId } },
    matches(selector) {
      return selector === '[data-area-move-preview-form]';
    },
  };
}

function moveConfirmTarget() {
  const button = {
    closest(selector) {
      if (selector === '[data-area-move-confirm]') return button;
      return null;
    },
  };
  return button;
}

function moveApi({ previewError = null } = {}) {
  const calls = [];
  let areaReadCount = 0;
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) {
        areaReadCount += 1;
        return { areas: areaReadCount === 1 ? moveNodes : movedNodes };
      }
      if (
        path === '/api/v1/areas/calahan/move-preview?new_parent_area_id=destination'
        && !options.method
      ) {
        if (previewError) throw previewError;
        return movePreview;
      }
      if (path === '/api/v1/areas/calahan/move' && options.method === 'POST') {
        return movePreview;
      }
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  return { api, calls, getAreaReadCount: () => areaReadCount };
}

async function openMoveEditor({ api, root }) {
  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaRowTarget('calahan'));
  await root.dispatch('click', areaActionTarget('move'));
}

test('Area branch move offers only active valid parents and excludes self or descendants client-side', async () => {
  const { api } = moveApi();
  const root = interactiveRoot();

  await openMoveEditor({ api, root });

  assert.match(root.innerHTML, /data-area-move-preview-form/);
  assert.match(root.innerHTML, /value="destination"/);
  assert.equal(root.innerHTML.includes('value="calahan"'), false);
  assert.equal(root.innerHTML.includes('value="balayong"'), false);
  assert.equal(root.innerHTML.includes('value="retired-destination"'), false);
});

test('Area move fetches server preview first and renders server-authoritative impact before Confirm', async () => {
  const { api, calls } = moveApi();
  const root = interactiveRoot();

  await openMoveEditor({ api, root });
  await root.dispatch('change', moveParentSelectTarget('destination'));
  await root.dispatch('submit', movePreviewFormTarget('destination'));

  const previews = calls.filter((call) => call.path.includes('/move-preview?'));
  const moves = calls.filter((call) => call.options.method === 'POST' && call.path.endsWith('/move'));
  assert.equal(previews.length, 1);
  assert.equal(
    previews[0].path,
    '/api/v1/areas/calahan/move-preview?new_parent_area_id=destination',
  );
  assert.equal(moves.length, 0, 'preview must never move the Area');

  // These deliberately differ from the tree counts so the Portal cannot infer them client-side.
  assert.match(root.innerHTML, /Clients affected:<\/strong>\s*23/i);
  assert.match(root.innerHTML, /Descendant Areas affected:<\/strong>\s*4/i);
  assert.match(root.innerHTML, /Collector before:<\/strong>\s*Collector A/i);
  assert.match(root.innerHTML, /Collector after:<\/strong>\s*Collector C/i);
  assert.match(root.innerHTML, /1[^<]*stale delegated access/i);
  assert.match(root.innerHTML, /data-area-move-confirm/);
});

test('Area move preview failure never exposes Confirm or sends a move POST', async () => {
  const previewError = new Error('authoritative move preview conflict');
  previewError.status = 409;
  const { api, calls } = moveApi({ previewError });
  const root = interactiveRoot();

  await openMoveEditor({ api, root });
  await root.dispatch('change', moveParentSelectTarget('destination'));
  await root.dispatch('submit', movePreviewFormTarget('destination'));

  const moves = calls.filter((call) => call.options.method === 'POST' && call.path.endsWith('/move'));
  assert.equal(moves.length, 0);
  assert.equal(root.innerHTML.includes('data-area-move-confirm'), false);
  assert.match(root.innerHTML, /conflict|refresh|preview/i);
});

test('Area branch move POST occurs only after one explicit Confirm and then reloads authoritative tree', async () => {
  const { api, calls, getAreaReadCount } = moveApi();
  const root = interactiveRoot();

  await openMoveEditor({ api, root });
  await root.dispatch('change', moveParentSelectTarget('destination'));
  await root.dispatch('submit', movePreviewFormTarget('destination'));

  assert.equal(
    calls.filter((call) => call.options.method === 'POST' && call.path.endsWith('/move')).length,
    0,
  );

  await root.dispatch('click', moveConfirmTarget());

  const moves = calls.filter((call) => call.options.method === 'POST' && call.path.endsWith('/move'));
  assert.equal(moves.length, 1);
  assert.equal(moves[0].path, '/api/v1/areas/calahan/move');
  assert.deepEqual(moves[0].options.body, { new_parent_area_id: 'destination' });
  assert.equal(getAreaReadCount(), 2, 'successful move must reload the authoritative Area tree');
  assert.match(root.innerHTML, /Morong › Destination › Calahan/);
});

test('Area branch move controls remain absent without area.manage', async () => {
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas') return { areas: moveNodes };
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });
  await root.dispatch('click', areaRowTarget('calahan'));

  assert.equal(root.innerHTML.includes('data-area-action="move"'), false);
  assert.equal(calls.some((call) => call.path.includes('/move-preview?')), false);
  assert.equal(calls.some((call) => call.options.method === 'POST' && call.path.endsWith('/move')), false);
});
