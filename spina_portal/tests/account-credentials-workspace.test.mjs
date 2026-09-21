import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { mountCollectorWorkspace } from '../assets/roles/collector.js';
import { Element, fire } from './helpers/dom.mjs';

const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace, collector: mountCollectorWorkspace };

function harness(role, permissions = []) {
  const controller = new AbortController();
  const context = {
    root: new Element(), session: { user: { role, roles: [role] }, permissions },
    signal: controller.signal, controller, calls: [], navigation: [],
  };
  context.root.dataset = {};
  context.setNavigation = (items) => { context.navigation = items; };
  context.api = { async request(path) { context.calls.push(path); return {}; } };
  return context;
}

for (const role of Object.keys(mounts)) {
  test(`${role}: own password controls are reachable from Account without administrative permissions`, async () => {
    const h = harness(role);
    await mounts[role](h);
    const section = h.root.querySelector(`#${role}-account`);
    assert.ok(section, 'every staff workspace must have an Account section');
    assert.ok(h.navigation.some((item) => item.id === `${role}-account`));
    const controls = section.querySelector('[data-account-credentials]');
    assert.ok(controls?.querySelector('[data-credential-own-form]'));
    assert.equal(controls.querySelector('[data-credential-search-form]'), null);
    assert.equal(h.calls.some((path) => path.includes('/password')), false);
    h.controller.abort();
    assert.equal(controls.innerHTML, '');
  });

  test(`${role}: workspace refresh clears old secret inputs and disables detached form submission`, async () => {
    const h = harness(role);
    await mounts[role](h);
    const controls = h.root.querySelector('[data-account-credentials]');
    assert.ok(controls, 'credential controls must be mounted');
    const form = controls.querySelector('[data-credential-own-form]');
    const input = form.querySelector('input[type="password"]');
    input.value = 'synthetic-password-to-clear';
    await mounts[role](h);
    assert.equal(input.value, '');
    assert.equal(controls.innerHTML, '');
    const before = h.calls.length;
    fire(form, 'submit');
    await setImmediate();
    assert.equal(h.calls.length, before, 'detached controls cannot change a password');
    h.controller.abort();
  });
}

test('Employee and Management reset tools are mounted only with the exact credential permission', async () => {
  for (const [role, permission] of [['employee', 'client.credential.manage'], ['management', 'account.manage']]) {
    const h = harness(role, [permission]);
    await mounts[role](h);
    assert.ok(h.root.querySelector('[data-account-credentials]')?.querySelector('[data-credential-search-form]'));
    h.controller.abort();
  }
});

test('the updated PWA shell includes the staff credential module for staff workspace imports', async () => {
  const worker = await readFile(new URL('../sw.js', import.meta.url), 'utf8');
  assert.match(worker, /spina-company-shell-v11/);
  assert.match(worker, /'\/assets\/account-credentials\.js'/);
});
