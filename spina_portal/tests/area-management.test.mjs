import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import * as areaManagementModule from '../assets/area-management.js';
import {
  areaKindLabel,
  buildAreaTree,
  filterAreaTree,
  renderAreaManagementShell,
} from '../assets/area-management.js';

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

const orderedNodes = [
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
    explicit_collector: collectorB,
    effective_collector: collectorB,
    effective_collector_source_area_id: 'nia',
    direct_client_count: 4,
    subtree_client_count: 4,
    child_count: 0,
  },
];

function childNames(node) {
  return node.children.map((child) => child.name);
}

function fakeRoot() {
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

function areaEditorTarget(kind, name) {
  return {
    dataset: { areaEditor: kind },
    elements: { name: { value: name } },
    matches(selector) {
      return selector === '[data-area-editor]';
    },
  };
}

test('Area tree preserves authoritative server sibling order', () => {
  const tree = buildAreaTree(orderedNodes);

  assert.equal(tree.length, 1);
  assert.equal(tree[0].name, 'Cardona');
  assert.deepEqual(childNames(tree[0].children[0]), ['Balayong', 'NIA']);
});

test('Area tree supports arbitrary hierarchy depth without a fixed Subarea limit', () => {
  const nodes = Array.from({ length: 7 }, (_, index) => ({
    area_id: `level-${index}`,
    parent_area_id: index === 0 ? null : `level-${index - 1}`,
    name: `Level ${index + 1}`,
    full_path: Array.from({ length: index + 1 }, (_unused, pathIndex) => `Level ${pathIndex + 1}`).join(' › '),
    depth: index,
    sort_order: 0,
    is_active: true,
    is_legacy_unmapped: false,
    explicit_collector: null,
    effective_collector: null,
    effective_collector_source_area_id: null,
  }));

  const tree = buildAreaTree(nodes);
  let cursor = tree[0];
  let visited = 1;
  while (cursor.children.length) {
    assert.equal(cursor.children.length, 1);
    cursor = cursor.children[0];
    visited += 1;
  }

  assert.equal(visited, 7);
  assert.equal(cursor.name, 'Level 7');
});

test('Area kind labels follow root, direct-child, deeper-child, and legacy rules', () => {
  const tree = buildAreaTree(orderedNodes);
  const city = tree[0];
  const barangay = city.children[0];
  const subarea = barangay.children[0];

  assert.equal(areaKindLabel(city, null), 'City/Municipality');
  assert.equal(areaKindLabel(barangay, city), 'Barangay');
  assert.equal(areaKindLabel(subarea, barangay), 'Subarea');

  const legacy = {
    ...city,
    area_id: 'legacy',
    name: 'Legacy Route Text',
    is_legacy_unmapped: true,
  };
  assert.equal(areaKindLabel(legacy, null), 'Legacy unmapped area');
});

test('Area search keeps NIA with Cardona and Calahan hierarchy context', () => {
  const filtered = filterAreaTree(buildAreaTree(orderedNodes), 'NIA');

  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].name, 'Cardona');
  assert.equal(filtered[0].children.length, 1);
  assert.equal(filtered[0].children[0].name, 'Calahan');
  assert.deepEqual(childNames(filtered[0].children[0]), ['NIA']);
});

test('Area search matches effective Collector name while preserving the matching branch', () => {
  const filtered = filterAreaTree(buildAreaTree(orderedNodes), 'Collector B');

  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].name, 'Cardona');
  assert.equal(filtered[0].children[0].name, 'Calahan');
  assert.deepEqual(childNames(filtered[0].children[0]), ['NIA']);
});

test('Area shell renders the shared two-panel boundary and escapes server text', () => {
  const tree = buildAreaTree([
    ...orderedNodes,
    {
      area_id: 'unsafe',
      parent_area_id: null,
      name: '<script>unsafe</script>',
      full_path: '<script>unsafe</script>',
      depth: 0,
      sort_order: 1,
      is_active: true,
      is_legacy_unmapped: false,
      explicit_collector: null,
      effective_collector: null,
      effective_collector_source_area_id: null,
    },
  ]);

  const html = renderAreaManagementShell({
    tree,
    selectedAreaId: 'cardona',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    query: '',
  });

  assert.match(html, /AREA MANAGEMENT/i);
  assert.match(html, /area-tree-panel/);
  assert.match(html, /area-details-panel/);
  assert.equal(html.includes('<script>unsafe</script>'), false);
  assert.match(html, /&lt;script&gt;unsafe&lt;\/script&gt;/);
});

test('selected Balayong details show inherited Collector, counts, state, and the authoritative path', () => {
  const html = renderAreaManagementShell({
    tree: buildAreaTree(orderedNodes),
    selectedAreaId: 'balayong',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    query: '',
  });

  assert.match(html, /Cardona › Calahan › Balayong/);
  assert.match(html, /Subarea/);
  assert.match(html, /Effective Collector:\s*<\/strong>\s*Collector A/);
  assert.match(html, /Inherited from:\s*<\/strong>\s*Calahan/);
  assert.match(html, /Direct Clients:\s*<\/span>\s*<strong>3<\/strong>/);
  assert.match(html, /Subtree Clients:\s*<\/span>\s*<strong>3<\/strong>/);
  assert.match(html, /Child Areas:\s*<\/span>\s*<strong>0<\/strong>/);
  assert.match(html, />Active<\/span>/);
});

test('normal Area screen never renders sensitive KYC, source-address, or photo content', () => {
  const html = renderAreaManagementShell({
    tree: buildAreaTree(orderedNodes),
    selectedAreaId: 'balayong',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    query: '',
  }).toLowerCase();

  for (const forbidden of [
    'national id',
    'tin id',
    'meralco',
    'source address',
    'location photo',
    '<img',
  ]) {
    assert.equal(html.includes(forbidden), false, `unexpected sensitive Area-screen content: ${forbidden}`);
  }
});

test('mountAreaManagement loads Area tree and Collector choices in parallel when permitted', async () => {
  assert.equal(typeof areaManagementModule.mountAreaManagement, 'function');

  const calls = [];
  const resolvers = new Map();
  const api = {
    request(path) {
      calls.push(path);
      return new Promise((resolve) => resolvers.set(path, resolve));
    },
  };
  const root = fakeRoot();
  const mounted = areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.collector.assign'] },
  });

  await Promise.resolve();
  assert.deepEqual(calls, ['/api/v1/areas', '/api/v1/areas/collectors']);

  resolvers.get('/api/v1/areas')({ areas: orderedNodes });
  resolvers.get('/api/v1/areas/collectors')({ collectors: [collectorA, collectorB] });
  await mounted;

  assert.match(root.innerHTML, /Cardona/);
  assert.match(root.innerHTML, /Collector A/);
});

test('mountAreaManagement skips Collector choices without area.collector.assign', async () => {
  assert.equal(typeof areaManagementModule.mountAreaManagement, 'function');

  const calls = [];
  const api = {
    async request(path) {
      calls.push(path);
      return { areas: orderedNodes };
    },
  };
  const root = fakeRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });

  assert.deepEqual(calls, ['/api/v1/areas']);
  assert.match(root.innerHTML, /Cardona/);
});

test('Area Management responsive CSS defines the shared tree and details layout boundary', () => {
  const css = readFileSync(new URL('../assets/app.css', import.meta.url), 'utf8');

  for (const selector of [
    '.area-management',
    '.area-tree-panel',
    '.area-details-panel',
    '.area-tree-row',
    '.area-tree-children',
    '.area-route-order-controls',
  ]) {
    assert.match(css, new RegExp(selector.replace('.', '\\.')));
  }
  assert.match(css, /@media/);
});

test('Area create controls use root, Barangay, and Subarea labels without classifying legacy nodes', () => {
  const tree = buildAreaTree(orderedNodes);
  const session = { permissions: ['area.manage'] };

  const cityHtml = renderAreaManagementShell({
    tree,
    selectedAreaId: 'cardona',
    expandedAreaIds: new Set(['cardona']),
    session,
  });
  assert.match(cityHtml, /data-area-action="add-root"/);
  assert.match(cityHtml, /\+ Add City\/Municipality/);
  assert.match(cityHtml, /data-area-action="add-child"/);
  assert.match(cityHtml, /\+ Add Barangay/);

  const barangayHtml = renderAreaManagementShell({
    tree,
    selectedAreaId: 'calahan',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    session,
  });
  assert.match(barangayHtml, /\+ Add Subarea/);

  const deepHtml = renderAreaManagementShell({
    tree,
    selectedAreaId: 'balayong',
    expandedAreaIds: new Set(['cardona', 'calahan']),
    session,
  });
  assert.match(deepHtml, /\+ Add Subarea/);

  const legacyTree = buildAreaTree([
    ...orderedNodes,
    {
      ...orderedNodes[0],
      area_id: 'legacy-route',
      name: 'Legacy Route Text',
      full_path: 'Legacy Route Text',
      sort_order: 1,
      is_legacy_unmapped: true,
    },
  ]);
  const legacyHtml = renderAreaManagementShell({
    tree: legacyTree,
    selectedAreaId: 'legacy-route',
    session,
  });
  assert.equal(/\+ Add (Barangay|Subarea)/.test(legacyHtml), false);
});

test('root Area create rejects blank names before I/O and posts a parentless authoritative request', async () => {
  const calls = [];
  let areaReadCount = 0;
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) {
        areaReadCount += 1;
        return { areas: orderedNodes };
      }
      if (path === '/api/v1/areas' && options.method === 'POST') return { area: {} };
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaActionTarget('add-root'));
  assert.match(root.innerHTML, /data-area-editor="create"/);

  const beforeBlank = calls.length;
  await root.dispatch('submit', areaEditorTarget('create', '   '));
  assert.equal(calls.length, beforeBlank);

  await root.dispatch('submit', areaEditorTarget('create', ' Taytay '));
  const createCall = calls.find(
    (call) => call.path === '/api/v1/areas' && call.options.method === 'POST',
  );
  assert.ok(createCall);
  assert.deepEqual(createCall.options.body, { parent_area_id: null, name: 'Taytay' });
  assert.equal(areaReadCount, 2, 'successful create must reload the authoritative tree');
});

test('City child create posts the selected City UID and exposes Add Barangay', async () => {
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) return { areas: orderedNodes };
      if (path === '/api/v1/areas' && options.method === 'POST') return { area: {} };
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaActionTarget('add-child'));
  assert.match(root.innerHTML, /\+ Add Barangay/);
  await root.dispatch('submit', areaEditorTarget('create', 'San Roque'));

  const createCall = calls.find(
    (call) => call.path === '/api/v1/areas' && call.options.method === 'POST',
  );
  assert.ok(createCall);
  assert.deepEqual(createCall.options.body, {
    parent_area_id: 'cardona',
    name: 'San Roque',
  });
});

test('Area rename rejects blank names, PATCHes the selected UID, reloads, and preserves selection', async () => {
  const calls = [];
  let areaReadCount = 0;
  const renamedNodes = orderedNodes.map((node) =>
    node.area_id === 'calahan'
      ? { ...node, name: 'Calahan Proper', full_path: 'Cardona › Calahan Proper' }
      : node,
  );
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) {
        areaReadCount += 1;
        return { areas: areaReadCount === 1 ? orderedNodes : renamedNodes };
      }
      if (path === '/api/v1/areas/calahan' && options.method === 'PATCH') return { area: {} };
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaRowTarget('calahan'));
  await root.dispatch('click', areaActionTarget('rename'));
  assert.match(root.innerHTML, /data-area-editor="rename"/);

  const beforeBlank = calls.length;
  await root.dispatch('submit', areaEditorTarget('rename', '   '));
  assert.equal(calls.length, beforeBlank);

  await root.dispatch('submit', areaEditorTarget('rename', ' Calahan Proper '));
  const renameCall = calls.find(
    (call) => call.path === '/api/v1/areas/calahan' && call.options.method === 'PATCH',
  );
  assert.ok(renameCall);
  assert.deepEqual(renameCall.options.body, { name: 'Calahan Proper' });
  assert.equal(areaReadCount, 2);
  assert.match(root.innerHTML, /area-tree-row selected/);
  assert.match(root.innerHTML, /<h3>Calahan Proper<\/h3>/);
});

test('Area 409 conflict stays on the prior tree and shows a safe conflict message', async () => {
  const conflict = new Error('Area name already exists under this parent.');
  conflict.status = 409;
  const api = {
    async request(path, options = {}) {
      if (path === '/api/v1/areas' && !options.method) return { areas: orderedNodes };
      if (path === '/api/v1/areas' && options.method === 'POST') throw conflict;
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  const root = interactiveRoot();

  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.manage'] },
  });
  await root.dispatch('click', areaActionTarget('add-root'));
  await root.dispatch('submit', areaEditorTarget('create', 'Cardona'));

  assert.match(root.innerHTML, /Cardona/);
  assert.match(root.innerHTML, /(already exists|conflict)/i);
});
