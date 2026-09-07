import assert from 'node:assert/strict';
import test from 'node:test';

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
  },
];

function childNames(node) {
  return node.children.map((child) => child.name);
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
