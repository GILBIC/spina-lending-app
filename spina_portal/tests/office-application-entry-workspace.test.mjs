import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111';
const APP = '22222222-2222-4222-8222-222222222222';
const VERSION = '33333333-3333-4333-8333-333333333333';
const CIF = '44444444-4444-4444-8444-444444444444';
const PRODUCT = '55555555-5555-4555-8555-555555555555';
const INTAKE = 'Office-Intake';
const REFERENCE = 'Loan/Exact-Ref';
const BASE = `/api/v1/management/clients/${CLIENT}/loan-applications`;
const LOOKUP = `/api/v1/management/onboarding/applicants/by-reference/${INTAKE}/cif-client`;
const SUMMARY = `${BASE}/by-reference/${encodeURIComponent(REFERENCE)}/review-summary`;
const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace };

function record(information, version = 1) {
  return { client_id: CLIENT, application_id: APP, application_version_id: VERSION,
    application_reference: REFERENCE, cif_version_id: CIF, cif_version_number: 2,
    version_number: version, requested_loan_type_name: 'Synthetic product',
    recorded_at: '2026-09-19T00:00:00Z', review_scope: 'loan_application_information_only',
    information, missing_fields: [] };
}
function information() {
  return { request: { requested_loan_type_id: PRODUCT, purpose: 'Private purpose', requested_amount: '9007199254740993.01',
    requested_payment_arrangement: 'Weekly', requested_term: 'Ten weeks', preferred_first_payment_date: null },
  repayment: { repayment_source: 'Business', source_details: 'Private source', monthly_gross_income: '0.00',
    monthly_net_income: '-50.25', has_existing_obligations: false, obligations: [] } };
}
function harness(role) {
  const h = { root: new Element(), controller: new AbortController(), requests: [], saved: record(information()), holdSave: null, saveError: null };
  h.context = { root: h.root, signal: h.controller.signal,
    session: { user: { role }, permissions: ['client_onboarding.requirement.review', 'area.manage'] },
    setNavigation() {}, api: { async request(path, options = {}) {
      h.requests.push({ path, options });
      if (path === LOOKUP) return { application_reference: INTAKE, client_id: CLIENT };
      if (path === `${BASE}/entry-context`) return { client_id: CLIENT, cif_version_id: CIF, cif_version_number: 2,
        loan_types: [{ id: PRODUCT, code: 'SYN', name: 'Synthetic product' }] };
      if (path === SUMMARY) return h.saved;
      if (options.method === 'POST') {
        if (h.saveError) throw h.saveError;
        if (h.holdSave) return h.holdSave;
        h.saved = record(options.body.information, options.body.expected_version_number ? options.body.expected_version_number + 1 : 1);
        if (h.saved.version_number > 1) h.saved.application_version_id = '66666666-6666-4666-8666-666666666666';
        const { cif_version_number, requested_loan_type_name, ...response } = h.saved;
        return response;
      }
      if (path === '/api/v1/areas') return { areas: [] };
      return {};
    } },
  };
  return h;
}
const button = (root, text) => root.querySelectorAll('button').find((b) => b.textContent === text);
const input = (root, name) => root.querySelector(`[name="${name}"]`);
function select(h) {
  const root = h.root.querySelector('[data-office-application-review]');
  input(root, 'intakeReference').value = INTAKE;
  input(root, 'applicationReference').value = REFERENCE;
  return root;
}
function set(root, name, value) { input(root, name).value = value; fire(input(root, name), 'input'); }
async function newEntry(h) {
  const root = select(h);
  fire(button(root, 'New application'), 'click');
  await setImmediate();
  return root.querySelector('[data-application-entry]');
}
function fill(entry) {
  for (const [name, value] of Object.entries(information().request)) set(entry, name, value ?? '');
  for (const [name, value] of Object.entries(information().repayment)) {
    if (name !== 'obligations') set(entry, name, value === false ? 'false' : value);
  }
}
function save(entry) { fire(entry.querySelector('form'), 'submit'); }
function posts(h) { return h.requests.filter((r) => r.options.method === 'POST'); }

for (const role of ['employee', 'management']) {
  test(`${role}: creates application with exact request values then refreshes authoritative review`, async (t) => {
    const h = harness(role); t.after(() => h.controller.abort());
    await mounts[role](h.context);
    const cif = h.root.querySelector('[data-office-cif-selection]').innerHTML;
    const area = h.root.querySelector(`#${role}-area-management`).innerHTML;
    const entry = await newEntry(h);
    fill(entry); save(entry); save(entry);
    await setImmediate();
    assert.equal(posts(h).length, 1);
    assert.deepEqual(posts(h)[0], { path: `${BASE}/drafts`, options: { method: 'POST', signal: h.controller.signal, body: {
      cif_version_id: CIF, application_reference: REFERENCE, information: information(),
    } } });
    assert.equal(h.requests.at(-1).path, SUMMARY);
    assert.match(h.root.textContent, /Private purpose/);
    assert.match(h.root.textContent, /9007199254740993\.01/);
    assert.equal(entry.innerHTML, '');
    assert.equal(h.root.querySelector('[data-office-cif-selection]').innerHTML, cif);
    assert.equal(h.root.querySelector(`#${role}-area-management`).innerHTML, area);
  });

  test(`${role}: appends from reviewed identity and version without modifying earlier facts`, async (t) => {
    const h = harness(role); t.after(() => h.controller.abort());
    await mounts[role](h.context);
    const root = select(h); fire(root.querySelector('form'), 'submit'); await setImmediate();
    fire(button(root, 'Edit application information'), 'click'); await setImmediate();
    const entry = root.querySelector('[data-application-entry]');
    assert.equal(input(entry, 'requested_amount').value, '9007199254740993.01');
    set(entry, 'purpose', 'Updated private purpose'); save(entry); await setImmediate();
    const expected = information(); expected.request.purpose = 'Updated private purpose';
    assert.deepEqual(posts(h)[0], { path: `${BASE}/${APP}/draft-versions`, options: { method: 'POST', signal: h.controller.signal, body: {
      cif_version_id: CIF, expected_version_number: 1, information: expected,
    } } });
    assert.match(root.textContent, /Updated private purpose/);
    assert.equal(h.saved.version_number, 2);
    assert.equal(h.requests.at(-1).path, SUMMARY);
  });

  for (const closeAction of ['Reload application', 'Cancel']) {
  test(`${role}: ${closeAction} after uncertain save reloads the reference and never replays POST`, async (t) => {
    const h = harness(role); t.after(() => h.controller.abort());
    h.saveError = Object.assign(new Error('Connection interrupted'), { status: 0 });
    await mounts[role](h.context);
    const entry = await newEntry(h); fill(entry); save(entry); await setImmediate();
    assert.equal(button(entry, 'Save application')?.disabled ?? true, true);
    assert.equal(posts(h).length, 1);
    fire(button(entry, closeAction), 'click'); await setImmediate();
    assert.equal(posts(h).length, 1);
    assert.equal(h.requests.at(-1).path, SUMMARY);
    assert.match(h.root.textContent, /Private purpose/);
  });
  }

  test(`${role}: changing reference clears form and ignores a late save callback`, async (t) => {
    const h = harness(role); t.after(() => h.controller.abort());
    let resolve; h.holdSave = new Promise((done) => { resolve = done; });
    await mounts[role](h.context);
    const entry = await newEntry(h); fill(entry); save(entry); await setImmediate();
    const oldField = input(entry, 'purpose');
    const root = h.root.querySelector('[data-office-application-review]');
    set(root, 'applicationReference', 'Another reference');
    assert.equal(entry.innerHTML, '');
    assert.equal(oldField.value, '');
    resolve(h.saved); await setImmediate();
    assert.doesNotMatch(root.textContent, /Private purpose/);
    assert.equal(h.requests.filter((r) => r.path === SUMMARY).length, 0);
    assert.equal(posts(h).length, 1);
  });

  test(`${role}: logout clears editor values while a save is pending`, async () => {
    const h = harness(role); let resolve;
    h.holdSave = new Promise((done) => { resolve = done; });
    await mounts[role](h.context);
    const entry = await newEntry(h); fill(entry); save(entry); await setImmediate();
    const oldField = input(entry, 'purpose'); h.controller.abort();
    resolve(h.saved); await setImmediate();
    assert.equal(oldField.value, '');
    assert.equal(h.root.querySelector('[data-office-application-review]').innerHTML, '');
    assert.equal(h.requests.filter((r) => r.path === SUMMARY).length, 0);
  });

  test(`${role}: stale detached edit button cannot open an editor for a changed selection`, async (t) => {
    const h = harness(role); t.after(() => h.controller.abort());
    await mounts[role](h.context);
    const root = select(h); fire(root.querySelector('form'), 'submit'); await setImmediate();
    const oldEdit = button(root, 'Edit application information');
    set(root, 'intakeReference', 'Other intake');
    fire(oldEdit, 'click'); await setImmediate();
    assert.equal(h.requests.some((r) => r.path.endsWith('/entry-context')), false);
    assert.equal(root.querySelector('[data-application-entry]').innerHTML, '');
  });
}
