import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildAreaTree,
  renderAreaManagementShell,
} from '../assets/area-management.js';

const tree = buildAreaTree([
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
    subtree_client_count: 1,
    child_count: 0,
  },
]);

const selectedClient = {
  client_id: 'client-001',
  client_code: 'SPN-0001',
  full_name: 'Jose Dela Cruz',
  area_id: 'balayong',
  area_path: 'Cardona › Calahan › Balayong',
  effective_collector: null,
};

const immediateTransfer = {
  client_id: 'client-001',
  old_area_id: 'balayong',
  old_area_path: 'Cardona › Calahan › Balayong',
  new_area_id: 'nia',
  new_area_path: 'Cardona › Calahan › NIA',
  effective_date: '2026-09-08',
  timing: 'immediate',
};

test('confirmed immediate Client transfer shows the target Area as current immediately', () => {
  const html = renderAreaManagementShell({
    tree,
    selectedAreaId: 'cardona',
    session: { permissions: ['area.client.assign'] },
    clientTransferEditor: {
      query: 'Jose Dela Cruz',
      results: [],
      selectedClient,
      targetAreaId: 'nia',
      preview: null,
      result: immediateTransfer,
      error: null,
    },
  });

  const resultStart = html.indexOf('area-client-transfer-result');
  assert.notEqual(resultStart, -1);
  const resultHtml = html.slice(resultStart);

  assert.match(resultHtml, /Transferred/);
  assert.match(resultHtml, /Effective:\s*Immediately/);
  assert.match(resultHtml, /Current Area:\s*Cardona › Calahan › NIA/i);
  assert.equal(
    /Current Area:\s*Cardona › Calahan › Balayong/i.test(resultHtml),
    false,
    'an immediate transfer must not keep the old Area labeled as current',
  );
});
