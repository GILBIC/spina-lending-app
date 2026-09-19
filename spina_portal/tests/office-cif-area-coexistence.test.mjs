import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const CIF_PERMISSION = 'client_onboarding.requirement.review';
const AREA_PERMISSION = 'area.manage';
const REFERENCE = 'APP-2026-000009';
const CLIENT_ID = '11111111-1111-4111-8111-111111111111';
const LOOKUP = `/api/v1/management/onboarding/applicants/by-reference/${REFERENCE}/cif-client`;
const SUMMARY = `/api/v1/management/clients/${CLIENT_ID}/cif/review-summary`;
const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace };

function harness(role, permissions) {
  const controller = new AbortController();
  const h = { controller, requests: [], navigation: [] };
  h.context = {
    root: new Element(),
    session: { user: { role, roles: [role], full_name: 'Synthetic office user' }, permissions },
    signal: controller.signal,
    setNavigation(items) { h.navigation = items; },
    api: {
      async request(path, options = {}) {
        h.requests.push({ path, options });
        if (path === '/api/v1/areas') return { areas: [{
          area_id: 'synthetic-city', parent_area_id: null,
          name: 'Synthetic City', full_path: 'Synthetic City', depth: 0,
          is_active: true, is_legacy_unmapped: false, sort_order: 0,
          child_count: 0, direct_client_count: 0, subtree_client_count: 0,
          explicit_collector: null, effective_collector: null,
        }] };
        if (path === LOOKUP) return { application_reference: REFERENCE, client_id: CLIENT_ID };
        if (path === SUMMARY) return {
          client_id: CLIENT_ID,
          cif_version_id: '22222222-2222-4222-8222-222222222222',
          version_number: 1, status: 'draft', liveness_status: 'pending',
          full_name: 'Synthetic CIF Applicant', phone_number: '09170000009',
          email: null, present_address: 'Synthetic CIF address',
          review_scope: 'cif_information_only',
        };
        return {};
      },
    },
  };
  return h;
}

function areaRequests(h) {
  return h.requests.filter(({ path }) => path.startsWith('/api/v1/areas'));
}

function cifRequests(h) {
  return h.requests.filter(({ path }) => path === LOOKUP || path === SUMMARY);
}

function assertAreaLoaded(h, role) {
  const area = h.context.root.querySelector(`#${role}-area-management`);
  assert.ok(area?.querySelector('.area-management'), 'shared Area Management must be mounted');
  assert.match(area.querySelector('h2').textContent, /Area Management/);
  assert.match(area.querySelector('.area-tree-row').textContent, /Synthetic City/);
  assert.deepEqual(areaRequests(h).map(({ path }) => path), ['/api/v1/areas']);
  assert.deepEqual(h.navigation.filter(({ id }) => id === `${role}-area-management`), [
    { id: `${role}-area-management`, label: 'Area Management' },
  ]);
  return area;
}

async function openCif(h, role) {
  const section = h.context.root.querySelector(`#${role}-cif-review`);
  const selection = section?.querySelector('[data-office-cif-selection]');
  assert.ok(selection?.querySelector('form'), 'office CIF selection must be mounted');
  assert.deepEqual(h.navigation.filter(({ id }) => id === `${role}-cif-review`), [
    { id: `${role}-cif-review`, label: 'CIF review' },
  ]);
  const input = selection.querySelector('input');
  input.value = REFERENCE;
  fire(input, 'input');
  assert.equal(fire(selection.querySelector('form'), 'submit').defaultPrevented, true);
  await setImmediate();
  assert.deepEqual(cifRequests(h).map(({ path }) => path), [LOOKUP, SUMMARY]);
  assert.match(selection.textContent, /Synthetic CIF Applicant/);
  assert.match(selection.textContent, /Synthetic CIF address/);
  for (const { options } of [...areaRequests(h), ...cifRequests(h)]) {
    assert.equal(options.method ?? 'GET', 'GET');
    assert.equal(options.body, undefined);
  }
}

for (const role of ['employee', 'management']) {
  test(`${role}: Area Management and CIF selection coexist without disrupting the CIF GET chain`, async (t) => {
    const h = harness(role, [AREA_PERMISSION, CIF_PERMISSION]);
    t.after(() => h.controller.abort());
    await mounts[role](h.context);
    const area = assertAreaLoaded(h, role);
    const areaBefore = area.innerHTML;
    assert.deepEqual(cifRequests(h), []);

    await openCif(h, role);

    assert.equal(h.context.root.querySelector(`#${role}-area-management`), area);
    assert.equal(area.innerHTML, areaBefore);
    assert.equal(areaRequests(h).length, 1);
  });

  test(`${role}: Area-only permission does not expose CIF even with a similar permission string`, async (t) => {
    const h = harness(role, [AREA_PERMISSION, `${CIF_PERMISSION}.extra`]);
    t.after(() => h.controller.abort());
    await mounts[role](h.context);

    assertAreaLoaded(h, role);
    assert.equal(h.context.root.querySelector(`#${role}-cif-review`), null);
    assert.equal(h.context.root.querySelector('[data-office-cif-selection]'), null);
    assert.equal(h.navigation.some(({ id }) => id === `${role}-cif-review`), false);
    assert.deepEqual(cifRequests(h), []);
  });

  test(`${role}: CIF-only permission never loads Area Management through a similar permission string`, async (t) => {
    const h = harness(role, [CIF_PERMISSION, `${AREA_PERMISSION}.extra`]);
    t.after(() => h.controller.abort());
    await mounts[role](h.context);

    await openCif(h, role);

    assert.equal(h.context.root.querySelector(`#${role}-area-management`), null);
    assert.equal(h.navigation.some(({ id }) => id === `${role}-area-management`), false);
    assert.deepEqual(areaRequests(h), []);
  });
}
