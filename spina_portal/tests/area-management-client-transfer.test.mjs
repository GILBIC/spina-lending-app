import assert from 'node:assert/strict';
import test from 'node:test';

import * as areaManagementModule from '../assets/area-management.js';

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

const areaNodes = [
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
    subtree_client_count: 1,
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
    explicit_collector: collectorB,
    effective_collector: collectorB,
    effective_collector_source_area_id: 'nia',
    direct_client_count: 0,
    subtree_client_count: 0,
    child_count: 0,
  },
];

const clientResult = {
  client_id: 'client-001',
  client_code: 'SPN-0001',
  full_name: 'Jose Dela Cruz',
  area_id: 'balayong',
  area_path: 'Cardona › Calahan › Balayong',
  effective_collector: collectorA,
};

const immediatePreview = {
  client_id: 'client-001',
  old_area_id: 'balayong',
  old_area_path: 'Cardona › Calahan › Balayong',
  new_area_id: 'nia',
  new_area_path: 'Cardona › Calahan › NIA',
  old_effective_collector_user_id: 'collector-a',
  new_effective_collector_user_id: 'collector-b',
  effective_date: '2026-09-08',
  timing: 'immediate',
};

const deferredPreview = {
  ...immediatePreview,
  effective_date: '2026-09-09',
  timing: 'next_collection_day',
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

function clientSearchFormTarget(query) {
  return {
    elements: { q: { value: query } },
    matches(selector) {
      return selector === '[data-area-client-search-form]';
    },
  };
}

function clientResultTarget(clientId) {
  const row = {
    dataset: { areaClientId: clientId },
    closest(selector) {
      if (selector === '[data-area-client-id]') return row;
      return null;
    },
  };
  return row;
}

function clientTransferPreviewFormTarget(targetAreaId) {
  return {
    elements: { target_area_id: { value: targetAreaId } },
    matches(selector) {
      return selector === '[data-area-client-transfer-preview-form]';
    },
  };
}

function clientTransferConfirmTarget() {
  const button = {
    closest(selector) {
      if (selector === '[data-area-client-transfer-confirm]') return button;
      return null;
    },
  };
  return button;
}

function transferApi({ preview = immediatePreview, previewError = null } = {}) {
  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path === '/api/v1/areas' && !options.method) return { areas: areaNodes };
      if (path === '/api/v1/areas/clients?q=Jose%20Dela%20Cruz' && !options.method) {
        return { clients: [clientResult] };
      }
      if (
        path === '/api/v1/clients/client-001/area-transfer-preview?target_area_id=nia'
        && !options.method
      ) {
        if (previewError) throw previewError;
        return preview;
      }
      if (path === '/api/v1/clients/client-001/area-transfer' && options.method === 'POST') {
        return preview;
      }
      throw new Error(`Unexpected Area request: ${path}`);
    },
  };
  return { api, calls };
}

async function openClientTransfer({ api, root }) {
  await areaManagementModule.mountAreaManagement({
    api,
    root,
    session: { permissions: ['area.client.assign'] },
  });
  await root.dispatch('click', areaActionTarget('client-transfer'));
}

async function searchAndSelectClient({ api, root }) {
  await openClientTransfer({ api, root });
  await root.dispatch('submit', clientSearchFormTarget('Jose Dela Cruz'));
  await root.dispatch('click', clientResultTarget('client-001'));
}

test('Client Area transfer searches operationally minimal Client results under exact area.client.assign', async () => {
  const { api, calls } = transferApi();
  const root = interactiveRoot();

  await openClientTransfer({ api, root });
  assert.match(root.innerHTML, /data-area-client-search-form/);

  await root.dispatch('submit', clientSearchFormTarget('Jose Dela Cruz'));

  assert.equal(
    calls.some((call) => call.path === '/api/v1/areas/clients?q=Jose%20Dela%20Cruz'),
    true,
  );
  assert.match(root.innerHTML, /Jose Dela Cruz/);
  assert.match(root.innerHTML, /SPN-0001/);
  assert.match(root.innerHTML, /Cardona › Calahan › Balayong/);
  assert.match(root.innerHTML, /Collector A/);

  const lower = root.innerHTML.toLowerCase();
  for (const forbidden of ['national id', 'tin id', 'meralco', 'location photo', '<img']) {
    assert.equal(lower.includes(forbidden), false, `unexpected sensitive Client-transfer content: ${forbidden}`);
  }
});

test('Client Area transfer renders the server immediate decision and never offers a manual timing choice', async () => {
  const { api, calls } = transferApi({ preview: immediatePreview });
  const root = interactiveRoot();

  await searchAndSelectClient({ api, root });
  await root.dispatch('submit', clientTransferPreviewFormTarget('nia'));

  assert.equal(
    calls.some(
      (call) => call.path === '/api/v1/clients/client-001/area-transfer-preview?target_area_id=nia',
    ),
    true,
  );
  assert.match(
    root.innerHTML,
    /Effective:\s*Immediately[^<]*no official collection has been recorded today/i,
  );
  assert.equal(root.innerHTML.includes('name="timing"'), false);
  assert.equal(/choose\s+(immediate|tomorrow)/i.test(root.innerHTML), false);
});

test('Client Area transfer renders the authoritative deferred date and reason without inventing timing', async () => {
  const { api } = transferApi({ preview: deferredPreview });
  const root = interactiveRoot();

  await searchAndSelectClient({ api, root });
  await root.dispatch('submit', clientTransferPreviewFormTarget('nia'));

  assert.match(
    root.innerHTML,
    /Effective:\s*Sep 9, 2026[^<]*next scheduled collection day because today already has an official collection/i,
  );
  assert.match(root.innerHTML, /Current Area:\s*Cardona › Calahan › Balayong/i);
  assert.match(root.innerHTML, /Target Area:\s*Cardona › Calahan › NIA/i);
});

test('next-collection-day-unavailable conflict shows no guessed date and never submits a transfer', async () => {
  const previewError = new Error(
    'SPINA could not find an authoritative next scheduled collection day for this Client. Refresh the schedule before retrying the Area transfer.',
  );
  previewError.status = 409;
  previewError.code = 'client_transfer_next_collection_day_unavailable';
  const { api, calls } = transferApi({ previewError });
  const root = interactiveRoot();

  await searchAndSelectClient({ api, root });
  await root.dispatch('submit', clientTransferPreviewFormTarget('nia'));

  assert.match(root.innerHTML, /next scheduled collection day/i);
  assert.equal(root.innerHTML.includes('data-area-client-transfer-confirm'), false);
  assert.equal(/Tomorrow|Sep\s+\d|2026-09-\d{2}/i.test(root.innerHTML), false);
  assert.equal(
    calls.some(
      (call) => call.path === '/api/v1/clients/client-001/area-transfer' && call.options.method === 'POST',
    ),
    false,
  );
});

test('confirmed deferred Client transfer submits one target Area, shows Scheduled, and keeps current Area until effective date', async () => {
  const { api, calls } = transferApi({ preview: deferredPreview });
  const root = interactiveRoot();

  await searchAndSelectClient({ api, root });
  await root.dispatch('submit', clientTransferPreviewFormTarget('nia'));
  await root.dispatch('click', clientTransferConfirmTarget());

  const submits = calls.filter(
    (call) => call.path === '/api/v1/clients/client-001/area-transfer' && call.options.method === 'POST',
  );
  assert.equal(submits.length, 1);
  assert.deepEqual(submits[0].options.body, { target_area_id: 'nia' });
  assert.equal(Object.hasOwn(submits[0].options.body, 'ancestor_area_ids'), false);
  assert.equal(Object.hasOwn(submits[0].options.body, 'timing'), false);
  assert.match(root.innerHTML, /Scheduled/i);
  assert.match(root.innerHTML, /Sep 9, 2026/);
  assert.match(root.innerHTML, /Current Area:\s*Cardona › Calahan › Balayong/i);
});
