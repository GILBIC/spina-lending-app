import assert from 'node:assert/strict';
import test from 'node:test';

import {
  areaKindLabel,
  buildAreaTree,
  renderAreaManagementShell,
} from '../assets/area-management.js';

const collector = {
  user_id: 'collector-1',
  username: 'collector.one',
  full_name: 'Gilbic Clarck San Jose',
};

const legacyLeaf = {
  area_id: 'legacy-second',
  parent_area_id: null,
  name: 'SECOND TEST AREA',
  full_path: 'SECOND TEST AREA',
  depth: 0,
  sort_order: 0,
  is_active: true,
  is_legacy_unmapped: true,
  explicit_collector: collector,
  effective_collector: collector,
  effective_collector_source_area_id: 'legacy-second',
  direct_client_count: 1,
  subtree_client_count: 1,
  child_count: 0,
};

const sibling = {
  ...legacyLeaf,
  area_id: 'legacy-gilbic',
  name: 'GILBIC TEST AREA',
  full_path: 'GILBIC TEST AREA',
  sort_order: 1,
  explicit_collector: {
    user_id: 'collector-2',
    username: 'collector.two',
    full_name: 'Test Collector',
  },
  effective_collector: {
    user_id: 'collector-2',
    username: 'collector.two',
    full_name: 'Test Collector',
  },
  effective_collector_source_area_id: 'legacy-gilbic',
};

const session = {
  permissions: [
    'area.manage',
    'area.collector.assign',
    'area.client.assign',
    'area.retire',
  ],
};

test('Area Management presents a legacy leaf Area without duplicate internal terminology', () => {
  const tree = buildAreaTree([legacyLeaf, sibling]);
  const html = renderAreaManagementShell({
    tree,
    selectedAreaId: 'legacy-second',
    expandedAreaIds: new Set(),
    query: '',
    session,
  });

  assert.equal(areaKindLabel(legacyLeaf, null), 'Legacy area');
  assert.doesNotMatch(html, /Legacy unmapped area/i);
  assert.doesNotMatch(html, /Effective Collector/i);
  assert.doesNotMatch(html, /Explicit Collector/i);
  assert.match(html, /Collector/);
  assert.match(html, /Gilbic Clarck San Jose/);
  assert.match(html, /Assigned directly/i);

  const selectedDetails = html.split('area-details-panel')[1] || '';
  assert.equal((selectedDetails.match(/SECOND TEST AREA/g) || []).length, 1);
  assert.doesNotMatch(selectedDetails, /Direct Clients/i);
  assert.doesNotMatch(selectedDetails, /Subtree Clients/i);
  assert.match(selectedDetails, /Clients/);
  assert.match(selectedDetails, />1</);
  assert.match(selectedDetails, /Child areas/i);
  assert.match(selectedDetails, />0</);
});

test('Area Management uses explicit action and search language', () => {
  const html = renderAreaManagementShell({
    tree: buildAreaTree([legacyLeaf, sibling]),
    selectedAreaId: 'legacy-second',
    expandedAreaIds: new Set(),
    query: '',
    session,
  });

  assert.match(html, /Search area or collector/i);
  assert.match(html, />Move Area</);
  assert.match(html, />Assign Collector</);
  assert.match(html, />Move Client</);
  assert.match(html, />Retire Area</);
  assert.doesNotMatch(html, />Move</);
  assert.doesNotMatch(html, />Collector</);
  assert.doesNotMatch(html, /authoritative server order/i);
  assert.match(html, /set collection route order/i);
});

test('Area reorder controls stay visually attached to their Area row', () => {
  const html = renderAreaManagementShell({
    tree: buildAreaTree([legacyLeaf, sibling]),
    selectedAreaId: 'legacy-second',
    expandedAreaIds: new Set(),
    query: '',
    session,
  });

  assert.match(
    html,
    /area-tree-row-shell[\s\S]*area-tree-row selected[\s\S]*area-tree-order-actions/,
  );
});
