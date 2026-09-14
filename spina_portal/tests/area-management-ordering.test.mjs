import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  buildAreaTree,
  mountAreaManagement,
  renderAreaManagementShell,
} from '../assets/area-management.js';

const collectorA = {
  user_id: 'collector-a',
  username: 'collector.a',
  full_name: 'Collector A',
};

const orderedSiblingIds = ['balayong', 'nia', 'main-calahan'];

const baseNodes = [
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
    subtree_client_count: 3,
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
    direct_client_count: 0,
    subtree_client_count: 3,
    child_count: 3,
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
    direct_client_count: 1,
    subtree_client_count: 1,
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
    direct_client_count: 1,
    subtree_client_count: 1,
    child_count: 0,
  },
  {
    area_id: 'main-calahan',
    parent_area_id: 'calahan',
    name: 'Main Calahan',
    full_path: 'Cardona › Calahan › Main Calahan',
    depth: 2,
    sort_order: 2,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: collectorA,
    effective_collector_source_area_id: 'calahan',
    direct_client_count: 1,
    subtree_client_count: 1,
    child_count: 0,
  },
];

function nodesInOrder(siblingIds = orderedSiblingIds) {
  const stable = baseNodes.slice(0, 2);
  const byId = new Map(baseNodes.slice(2).map((node) => [node.area_id, node]));
  return [
    ...stable,
    ...siblingIds.map((areaId, index) => ({ ...byId.get(areaId), sort_order: index })),
  ];
}

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
    async dispatch(type, target, extra = {}) {
      const event = {
        target,
        preventDefault() {},
        ...extra,
      };
      for (const handler of listeners.get(type) || []) {
        await handler(event);
      }
    },
  };
}

function orderTarget(areaId, direction) {
  const button = {
    dataset: { areaId, areaOrder: direction },
    closest(selector) {
      if (selector === '[data-area-order]') return button;
      return null;
    },
  };
  return button;
}

function dragTarget(areaId, parentAreaId) {
  const row = {
    dataset: { areaId, areaParentId: parentAreaId },
    closest(selector) {
      if (selector === '[data-area-id]') return row;
      return null;
    },
  };
  return row;
}

function disabledOrderButton(html, areaId, direction) {
  return new RegExp(
    `<button(?=[^>]*data-area-order="${direction}")(?=[^>]*data-area-id="${areaId}")(?=[^>]*disabled)[^>]*>`,
  ).test(html);
}

function orderingApi(initialOrder = orderedSiblingIds) {
  const calls = [];
  let serverOrder = [...initialOrder];
  return {
    calls,
    api: {
      async request(path, options = {}) {
        calls.push({ path, options });
        if (path === '/api/v1/areas' && !options.method) {
          return { areas: nodesInOrder(serverOrder) };
        }
        if (path === '/api/v1/areas/reorder' && options.method === 'POST') {
          serverOrder = [...options.body.ordered_area_ids];
          return { ordered_area_ids: [...serverOrder] };
        }
        throw new Error(`Unexpected Area request: ${path}`);
      },
    },
  };
}

test('Area route order renders accessible Up/Down fallback and same-parent drag handles', () => {
  const html = renderAreaManagementShell({
    tree: buildAreaTree(nodesInOrder()),
    selectedAreaId: 'calahan',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    session: { permissions: ['area.manage'] },
  });

  for (const areaId of orderedSiblingIds) {
    assert.match(html, new RegExp(`data-area-id="${areaId}"`));
    assert.match(html, new RegExp(`data-area-parent-id="calahan"`));
    assert.match(html, /draggable="true"/);
  }

  assert.equal(disabledOrderButton(html, 'balayong', 'up'), true);
  assert.equal(disabledOrderButton(html, 'main-calahan', 'down'), true);
  assert.equal(disabledOrderButton(html, 'balayong', 'down'), false);
  assert.equal(disabledOrderButton(html, 'main-calahan', 'up'), false);
});

test('Down and Up submit the complete authoritative sibling set in the requested order', async () => {
  {
    const { api, calls } = orderingApi();
    const root = interactiveRoot();
    await mountAreaManagement({ api, root, session: { permissions: ['area.manage'] } });

    await root.dispatch('click', orderTarget('balayong', 'down'));

    const reorder = calls.find(
      (call) => call.path === '/api/v1/areas/reorder' && call.options.method === 'POST',
    );
    assert.ok(reorder);
    assert.deepEqual(reorder.options.body, {
      parent_area_id: 'calahan',
      ordered_area_ids: ['nia', 'balayong', 'main-calahan'],
    });
  }

  {
    const { api, calls } = orderingApi();
    const root = interactiveRoot();
    await mountAreaManagement({ api, root, session: { permissions: ['area.manage'] } });

    await root.dispatch('click', orderTarget('main-calahan', 'up'));

    const reorder = calls.find(
      (call) => call.path === '/api/v1/areas/reorder' && call.options.method === 'POST',
    );
    assert.ok(reorder);
    assert.deepEqual(reorder.options.body, {
      parent_area_id: 'calahan',
      ordered_area_ids: ['balayong', 'main-calahan', 'nia'],
    });
  }
});

test('drag reorder changes only siblings under the same parent and never reparents a node', async () => {
  const otherParentNodes = [
    ...nodesInOrder(),
    {
      ...baseNodes[0],
      area_id: 'taytay',
      name: 'Taytay',
      full_path: 'Taytay',
      sort_order: 1,
    },
    {
      ...baseNodes[2],
      area_id: 'taytay-proper',
      parent_area_id: 'taytay',
      name: 'Taytay Proper',
      full_path: 'Taytay › Taytay Proper',
      depth: 1,
      sort_order: 0,
    },
  ];
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) return { areas: otherParentNodes };
      if (path === '/api/v1/areas/reorder' && options.method === 'POST') {
        return { ordered_area_ids: options.body.ordered_area_ids };
      }
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();
  await mountAreaManagement({ api, root, session: { permissions: ['area.manage'] } });

  await root.dispatch('dragstart', dragTarget('balayong', 'calahan'));
  await root.dispatch('drop', dragTarget('nia', 'calahan'));

  const reordersAfterSiblingDrop = calls.filter(
    (call) => call.path === '/api/v1/areas/reorder' && call.options.method === 'POST',
  );
  assert.equal(reordersAfterSiblingDrop.length, 1);
  assert.deepEqual(reordersAfterSiblingDrop[0].options.body, {
    parent_area_id: 'calahan',
    ordered_area_ids: ['nia', 'balayong', 'main-calahan'],
  });

  await root.dispatch('dragstart', dragTarget('balayong', 'calahan'));
  await root.dispatch('drop', dragTarget('taytay-proper', 'taytay'));

  const reordersAfterCrossParentDrop = calls.filter(
    (call) => call.path === '/api/v1/areas/reorder' && call.options.method === 'POST',
  );
  assert.equal(reordersAfterCrossParentDrop.length, 1);
});

test('Area ordering source never alphabetically re-sorts the server-authoritative tree', () => {
  const source = readFileSync(new URL('../assets/area-management.js', import.meta.url), 'utf8');
  assert.equal(/\.sort\([^\n]*name/i.test(source), false);
});
