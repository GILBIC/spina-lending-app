import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const PERMISSION = 'client_onboarding.requirement.review';
const REFERENCE = 'APP-2026-000001';
const CLIENT_ID = '11111111-1111-4111-8111-111111111111';
const LOOKUP = `/api/v1/management/onboarding/applicants/by-reference/${REFERENCE}/cif-client`;
const SUMMARY = `/api/v1/management/clients/${CLIENT_ID}/cif/review-summary`;
const PII = 'Synthetic Office Applicant';
const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace };

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function summary() {
  return {
    client_id: CLIENT_ID,
    cif_version_id: '22222222-2222-4222-8222-222222222222',
    version_number: 1,
    status: 'draft',
    liveness_status: 'pending',
    full_name: PII,
    phone_number: '09170000001',
    email: null,
    present_address: 'Synthetic Office Applicant Address',
    review_scope: 'cif_information_only',
  };
}

function harness(role, permissions = [PERMISSION]) {
  const controller = new AbortController();
  const requests = [];
  const h = {
    controller, requests, navigation: [],
    accountPending: null, summaryPending: null,
  };
  h.context = {
    root: new Element(),
    session: { user: { role, roles: [role], full_name: 'Office user' }, permissions },
    signal: controller.signal,
    setNavigation(items) { h.navigation = items; },
    api: {
      async request(path, options = {}) {
        requests.push({ path, options });
        if (path === '/api/v1/account') return h.accountPending?.promise ?? {};
        if (path === LOOKUP) return { application_reference: REFERENCE, client_id: CLIENT_ID };
        if (path === SUMMARY) return h.summaryPending?.promise ?? summary();
        return {};
      },
    },
  };
  return h;
}

function officeSelection(h, role) {
  const section = h.context.root.querySelector(`#${role}-cif-review`);
  assert.ok(section, `${role} office CIF review section is not connected`);
  assert.match(section.querySelector('h2').textContent, /CIF information review/);
  const selectionRoot = section.querySelector('[data-office-cif-selection]');
  assert.ok(selectionRoot?.querySelector('form'), `${role} office reference form is not connected`);
  return selectionRoot;
}

function openReview(selectionRoot) {
  const input = selectionRoot.querySelector('input');
  input.value = REFERENCE;
  fire(input, 'input');
  const event = fire(selectionRoot.querySelector('form'), 'submit');
  assert.equal(event.defaultPrevented, true);
}

function officeRequests(h) {
  return h.requests.filter(({ path }) => path === LOOKUP || path === SUMMARY);
}

for (const role of ['employee', 'management']) {
  test(`${role}: permitted workspace connects navigation and the office reference form`, async () => {
    const h = harness(role);
    await mounts[role](h.context);

    assert.deepEqual(h.navigation.find(({ id }) => id === `${role}-cif-review`), {
      id: `${role}-cif-review`, label: 'CIF review',
    }, `${role} CIF review navigation is not connected`);
    const root = officeSelection(h, role);
    assert.match(root.querySelector('label').textContent, /Office intake reference/);
    assert.equal(typeof h.context.officeCifCleanup, 'function');
    assert.deepEqual(officeRequests(h), []);
    h.context.officeCifCleanup();
  });

  for (const permissions of [[], [`${PERMISSION}.extra`]]) {
    test(`${role}: ${permissions.length ? 'similar' : 'missing'} permission exposes no CIF navigation or lookup`, async () => {
      const h = harness(role, permissions);
      await mounts[role](h.context);

      assert.equal(h.navigation.some(({ id }) => id === `${role}-cif-review`), false);
      assert.equal(h.context.root.querySelector('[data-office-cif-selection]'), null);
      assert.doesNotMatch(h.context.root.textContent, /Office intake reference/);
      assert.deepEqual(officeRequests(h), []);
    });
  }

  test(`${role}: submitting the workspace form renders the read-only CIF through the exact GET chain`, async () => {
    const h = harness(role);
    await mounts[role](h.context);
    const root = officeSelection(h, role);
    openReview(root);
    await setImmediate();

    assert.deepEqual(officeRequests(h).map(({ path }) => path), [LOOKUP, SUMMARY]);
    for (const { options } of officeRequests(h)) {
      assert.equal(options.method ?? 'GET', 'GET');
      assert.equal(options.body, undefined);
    }
    assert.match(root.textContent, /Synthetic Office Applicant/);
    assert.equal(root.querySelectorAll('input').length, 1);
    h.context.officeCifCleanup();
  });

  test(`${role}: remount immediately disposes old selection and ignores detached events and late summary`, async () => {
    const h = harness(role);
    h.summaryPending = deferred();
    await mounts[role](h.context);
    const oldRoot = officeSelection(h, role);
    const oldForm = oldRoot.querySelector('form');
    const oldInput = oldRoot.querySelector('input');
    openReview(oldRoot);
    await setImmediate();
    assert.deepEqual(officeRequests(h).map(({ path }) => path), [LOOKUP, SUMMARY]);

    h.accountPending = deferred();
    const remount = mounts[role](h.context);
    assert.equal(oldInput.value, '', 'starting workspace remount must clear the previous reference');
    assert.equal(oldRoot.innerHTML, '', 'starting workspace remount must dispose the previous form');
    oldInput.value = REFERENCE;
    fire(oldInput, 'input');
    fire(oldForm, 'submit');
    await setImmediate();
    assert.equal(officeRequests(h).length, 2);

    h.accountPending.resolve({});
    await remount;
    const newRoot = officeSelection(h, role);
    assert.notEqual(newRoot, oldRoot);
    assert.equal(newRoot.querySelector('input').value, '');
    const current = h.context.root.innerHTML;
    h.summaryPending.resolve(summary());
    await setImmediate();
    assert.equal(h.context.root.innerHTML, current);
    assert.equal(oldRoot.innerHTML, '');
    assert.doesNotMatch(h.context.root.textContent, /Synthetic Office Applicant/);
    h.context.officeCifCleanup();
  });

  test(`${role}: workspace AbortSignal clears the displayed review and detaches its form`, async () => {
    const h = harness(role);
    await mounts[role](h.context);
    const root = officeSelection(h, role);
    const form = root.querySelector('form');
    const input = root.querySelector('input');
    openReview(root);
    await setImmediate();
    assert.match(root.textContent, /Synthetic Office Applicant/);

    h.controller.abort();

    assert.equal(root.innerHTML, '');
    assert.equal(input.value, '');
    assert.doesNotMatch(h.context.root.textContent, /Synthetic Office Applicant/);
    fire(form, 'submit');
    await setImmediate();
    assert.equal(officeRequests(h).length, 2);
  });
}
