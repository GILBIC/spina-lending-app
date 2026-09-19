import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { availableRoleActions } from '../assets/roles.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { mountCollectorWorkspace } from '../assets/roles/collector.js';
import { Element, fire } from './helpers/dom.mjs';

const OFFICE = 'client_onboarding.requirement.review', VISIT = 'client_onboarding.visit.record';
const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace, collector: mountCollectorWorkspace };
function harness(role, permissions) {
  const h = { root: new Element(), session: { user: { role }, permissions }, calls: [], navigation: [], controller: new AbortController() };
  h.root.dataset = {}; h.signal = h.controller.signal;
  h.setNavigation = (items) => { h.navigation = items; };
  h.api = { async request(path) { h.calls.push(path); if (path.includes('/by-reference/')) throw new Error('Synthetic lookup complete'); return {}; } };
  return h;
}
for (const role of ['employee', 'management', 'collector']) {
  const permission = role === 'collector' ? VISIT : OFFICE;
  const selector = role === 'collector' ? '[data-collector-onboarding]' : '[data-office-onboarding]';
  const suffix = role === 'collector' ? 'visit-case' : 'case';
  const prefix = role === 'collector' ? 'collector' : 'management';
  test(`${role}: exact onboarding permission connects only its scoped case lookup`, async () => {
    const h = harness(role, [permission]); await mounts[role](h);
    const area = h.root.querySelector(selector); assert.ok(area);
    assert.ok(h.navigation.some(item => item.id === `${role}-onboarding`));
    assert.equal(h.calls.some(path => path.includes('/onboarding/')), false);
    area.querySelector('[name="applicationReference"]').value = ' Intake / Case ';
    fire(area.querySelector('[data-case-lookup]'), 'submit'); await setImmediate();
    assert.equal(h.calls.at(-1), `/api/v1/${prefix}/onboarding/applicants/by-reference/Intake%20%2F%20Case/${suffix}`);
    const catalog = availableRoleActions(role, [permission]).filter(item => item.key === `${role}-onboarding`);
    assert.equal(catalog.length, 1); assert.equal(catalog[0].permission, permission);
    assert.ok(catalog[0].path.endsWith(`/${suffix}`));
    h.controller.abort(); assert.equal(area.innerHTML, '');
  });
  test(`${role}: unrelated and similarly named permissions do not expose onboarding`, async () => {
    const permissions = [`${permission}.extra`, role === 'collector' ? OFFICE : VISIT];
    const h = harness(role, permissions); await mounts[role](h);
    assert.equal(h.root.querySelector(selector), null);
    assert.equal(h.navigation.some(item => item.id === `${role}-onboarding`), false);
    assert.equal(availableRoleActions(role, permissions).some(item => item.key === `${role}-onboarding`), false);
    assert.equal(h.calls.some(path => path.includes('/onboarding/')), false); h.controller.abort();
  });
  test(`${role}: workspace refresh disposes the old lookup before rendering the replacement`, async () => {
    const h = harness(role, [permission]); await mounts[role](h);
    const area = h.root.querySelector(selector), input = area.querySelector('[name="applicationReference"]'), form = area.querySelector('[data-case-lookup]');
    input.value = 'Private old reference'; await mounts[role](h);
    assert.equal(area.innerHTML, ''); assert.equal(input.value, '');
    const count = h.calls.length; fire(form, 'submit'); await setImmediate(); assert.equal(h.calls.length, count);
    assert.equal(h.root.querySelector(selector).querySelector('[name="applicationReference"]').value, ''); h.controller.abort();
  });
}
