import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { availableRoleActions } from '../assets/roles.js';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const permission = 'client_onboarding.requirement.review';
for (const [role, mount] of [['employee', mountEmployeeWorkspace], ['management', mountManagementWorkspace]]) {
  function harness(permissions = [permission]) {
    const h = {root: new Element(), session: {user: {role}, permissions}, calls: [], navigation: [], controller: new AbortController()};
    h.root.dataset = {}; h.signal = h.controller.signal;
    h.setNavigation = (items) => { h.navigation = items; };
    h.api = {async request(path) { h.calls.push(path); if (path.includes('/by-reference/')) throw new Error('Synthetic lookup complete'); return {}; }};
    return h;
  }

  test(`${role}: exact permission connects first-loan workspace without background financial requests`, async () => {
    const h = harness(); await mount(h);
    const area = h.root.querySelector('[data-office-first-loan]'); assert.ok(area);
    assert.ok(h.navigation.some(item => item.id === `${role}-first-loan`));
    assert.ok(availableRoleActions(role, [permission]).some(item => item.key === `${role}-first-loan`));
    assert.equal(h.calls.some(path => path.includes('/first-loans/')), false);
    area.querySelector('[name="intakeReference"]').value = 'Intake / Mixed';
    area.querySelector('[name="applicationReference"]').value = 'Application / Mixed';
    fire(area.querySelector('form'), 'submit'); await setImmediate();
    assert.equal(h.calls.at(-1), '/api/v1/management/onboarding/applicants/by-reference/Intake%20%2F%20Mixed/cif-client');
    h.controller.abort(); assert.equal(area.innerHTML, '');
  });

  test(`${role}: unrelated permission exposes no first-loan workflow`, async () => {
    const h = harness([`${permission}.extra`, 'account.manage']); await mount(h);
    assert.equal(h.root.querySelector('[data-office-first-loan]'), null);
    assert.equal(h.navigation.some(item => item.id === `${role}-first-loan`), false);
    assert.equal(availableRoleActions(role, h.session.permissions).some(item => item.key === `${role}-first-loan`), false);
    h.controller.abort();
  });

  test(`${role}: refresh erases old first-loan references and detaches previous actions`, async () => {
    const h = harness(); await mount(h);
    const area = h.root.querySelector('[data-office-first-loan]'), form = area.querySelector('form'), input = area.querySelector('[name="intakeReference"]');
    input.value = 'Private reference'; await mount(h);
    assert.equal(input.value, ''); assert.equal(area.innerHTML, '');
    const count = h.calls.length; fire(form, 'submit'); await setImmediate(); assert.equal(h.calls.length, count);
    h.controller.abort();
  });
}
