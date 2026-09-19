import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { ApiError } from '../assets/api.js';
import { mountOfficeCifSelection } from '../assets/office-cif-selection.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111';
const CIF = '22222222-2222-4222-8222-222222222222';
const REFERENCE = 'APP-OFFICE-TEST';
const SUMMARY = `/api/v1/management/clients/${CLIENT}/cif/review-summary`;
const EDIT = `${SUMMARY}?include_correction_availability=true&include_identity_information=true`;
const PATCH = `/api/v1/management/clients/${CLIENT}/cif/draft-information`;
const LOOKUP = `/api/v1/management/onboarding/applicants/by-reference/${REFERENCE}/cif-client`;

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function button(root, label) {
  const target = root.querySelectorAll('button').find((item) => item.textContent === label);
  assert.ok(target, `Missing ${label} button`);
  return target;
}

function harness(role = 'employee') {
  const h = {
    root: new Element(), requests: [], controller: new AbortController(),
    record: { client_id: CLIENT, cif_version_id: CIF, version_number: 2,
      status: 'draft', liveness_status: 'pending', review_scope: 'cif_information_only',
      full_name: '  Original Applicant  ', phone_number: '09170000001', email: null,
      present_address: 'Original private address' },
  };
  h.api = { async request(path, options = {}) {
    h.requests.push({ path, options });
    if (path === LOOKUP) return { application_reference: REFERENCE, client_id: CLIENT };
    if (path === SUMMARY) return { ...h.record };
    if (path === EDIT) {
      if (h.editError) throw h.editError;
      return { ...h.record, can_correct_information: true };
    }
    if (path === PATCH) {
      if (h.pendingSave) return h.pendingSave.promise;
      h.record = { ...h.record, ...options.body.corrected_information };
      return { ...h.record };
    }
    throw new Error(`Unexpected request ${path}`);
  } };
  h.dispose = mountOfficeCifSelection({ root: h.root, api: h.api,
    session: { user: { role }, permissions: ['client_onboarding.requirement.review'] },
    signal: h.controller.signal });
  return h;
}

async function open(h) {
  const input = h.root.querySelector('[name="applicationReference"]');
  input.value = REFERENCE;
  fire(input, 'input');
  fire(h.root.querySelector('form'), 'submit');
  await setImmediate();
  assert.deepEqual(h.requests.map((r) => r.path), [LOOKUP, SUMMARY]);
}

async function edit(h) {
  fire(button(h.root, 'Correct information'), 'click');
  await setImmediate();
  assert.equal(h.root.querySelector('[data-office-cif-review]').innerHTML, '');
  return h.root.querySelector('[data-office-cif-correction]');
}

function save(root) {
  root.querySelector('[name="full_name"]').value = 'Corrected Applicant';
  root.querySelector('[name="reason"]').value = 'Applicant corrected the recorded name';
  fire(root.querySelector('form'), 'submit');
}

for (const role of ['employee', 'management']) {
  test(`${role}: complete correction refreshes the selected read-only CIF after one PATCH`, async (t) => {
    const h = harness(role);
    t.after(h.dispose);
    const original = { full_name: h.record.full_name, phone_number: h.record.phone_number,
      email: h.record.email, present_address: h.record.present_address };
    await open(h);
    const editor = await edit(h);
    save(editor);
    await setImmediate();

    assert.deepEqual(h.requests.map((r) => r.path), [LOOKUP, SUMMARY, EDIT, PATCH, SUMMARY]);
    const write = h.requests.find((r) => r.path === PATCH).options;
    assert.equal(write.method, 'PATCH');
    assert.equal(write.body.cif_version_id, CIF);
    assert.deepEqual(write.body.expected_information, original);
    assert.equal(write.body.corrected_information.email, null);
    assert.match(h.root.querySelector('[data-office-cif-review]').textContent, /Corrected Applicant/);
    assert.equal(editor.querySelector('form'), null);
  });
}

test('Cancel clears the editor and reloads the current authoritative summary', async (t) => {
  const h = harness();
  t.after(h.dispose);
  await open(h);
  const editor = await edit(h);
  h.record.full_name = 'Name updated by another staff member';
  fire(button(editor, 'Cancel'), 'click');
  await setImmediate();
  assert.equal(h.requests.some((r) => r.path === PATCH), false);
  assert.match(h.root.querySelector('[data-office-cif-review]').textContent, /Name updated by another staff member/);
  assert.equal(editor.querySelector('form'), null);
});

for (const action of ['Clear', 'abort']) {
  test(`${action} makes a pending correction response unable to restore applicant data`, async (t) => {
    const h = harness();
    t.after(h.dispose);
    h.pendingSave = deferred();
    await open(h);
    const editor = await edit(h);
    save(editor);
    await setImmediate();
    assert.equal(h.requests.filter((r) => r.path === PATCH).length, 1);
    if (action === 'Clear') fire(button(h.root, 'Clear'), 'click');
    else h.controller.abort();
    h.pendingSave.resolve({ ...h.record, full_name: 'Late response applicant' });
    await setImmediate();
    assert.doesNotMatch(h.root.textContent, /Original Applicant|Original private address|Late response applicant/);
    assert.equal(h.requests.filter((r) => r.path === SUMMARY).length, 1);
    assert.equal(editor.innerHTML, '');
  });
}

test('correction access denial clears the selection and all applicant information', async (t) => {
  const h = harness();
  t.after(h.dispose);
  await open(h);
  h.editError = new ApiError('Permission revoked', { status: 403 });
  fire(button(h.root, 'Correct information'), 'click');
  await setImmediate();
  assert.equal(h.root.querySelector('[name="applicationReference"]').value, '');
  assert.equal(h.root.querySelector('[data-office-cif-review]').innerHTML, '');
  assert.equal(h.root.querySelector('[data-office-cif-correction]').innerHTML, '');
  assert.match(h.root.textContent, /Office access is no longer available/);
  assert.equal(h.requests.some((r) => r.path === PATCH), false);
});

test('an invalid initial review never exposes correction controls', async (t) => {
  const h = harness();
  t.after(h.dispose);
  h.record.client_id = CIF;
  await open(h);
  assert.equal(h.root.querySelector('[data-office-cif-correction]').innerHTML, '');
  assert.match(h.root.querySelector('[data-office-cif-review]').textContent, /invalid or does not match/);
});
