import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { mountEmployeeWorkspace } from '../assets/roles/employee.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111';
const INTAKE = 'APP-INTAKE-TEST';
const APPLICATION = 'Loan-Review/Test';
const PERMISSION = 'client_onboarding.requirement.review';
const LOOKUP = `/api/v1/management/onboarding/applicants/by-reference/${INTAKE}/cif-client`;
const REVIEW = `/api/v1/management/clients/${CLIENT}/loan-applications/by-reference/${encodeURIComponent(APPLICATION)}/review-summary`;
const mounts = { employee: mountEmployeeWorkspace, management: mountManagementWorkspace };

function summary() {
  return { client_id: CLIENT, application_id: '22222222-2222-4222-8222-222222222222',
    application_version_id: '33333333-3333-4333-8333-333333333333',
    application_reference: APPLICATION, cif_version_id: '44444444-4444-4444-8444-444444444444',
    version_number: 3, cif_version_number: 1, requested_loan_type_name: 'Synthetic product',
    recorded_at: '2026-09-19T00:00:00Z', review_scope: 'loan_application_information_only',
    information: {
      request: { requested_loan_type_id: '55555555-5555-4555-8555-555555555555', purpose: 'Private application purpose',
        requested_amount: '9007199254740993.01', requested_payment_arrangement: 'Weekly',
        requested_term: 'Eight weeks', preferred_first_payment_date: null },
      repayment: { repayment_source: 'Employment', source_details: 'Private employer details',
        monthly_gross_income: '0.00', monthly_net_income: '-50.25', has_existing_obligations: false, obligations: [] },
    }, missing_fields: [] };
}

function harness(role, permissions = [PERMISSION, 'area.manage']) {
  const h = { root: new Element(), requests: [], navigation: [], controller: new AbortController(), holdReview: null };
  h.context = { root: h.root, signal: h.controller.signal,
    session: { user: { role, full_name: 'Synthetic Staff' }, permissions },
    setNavigation(items) { h.navigation = items; },
    api: { async request(path, options = {}) {
      h.requests.push({ path, options });
      if (path === LOOKUP) return { application_reference: INTAKE, client_id: CLIENT };
      if (path === REVIEW) return h.holdReview || summary();
      if (path === '/api/v1/areas') return { areas: [] };
      return {};
    } },
  };
  return h;
}

function open(h) {
  const root = h.root.querySelector('[data-office-application-review]');
  assert.ok(root, 'application review is not connected');
  root.querySelector('[name="intakeReference"]').value = INTAKE;
  root.querySelector('[name="applicationReference"]').value = APPLICATION;
  fire(root.querySelector('form'), 'submit');
  return root;
}

for (const role of ['employee', 'management']) {
  test(`${role}: application review navigation connects the exact GET chain alongside CIF and Area`, async (t) => {
    const h = harness(role);
    t.after(() => h.controller.abort());
    await mounts[role](h.context);
    assert.deepEqual(h.navigation.find((item) => item.id === `${role}-application-review`), {
      id: `${role}-application-review`, label: 'Application review',
    });
    const cif = h.root.querySelector('[data-office-cif-selection]');
    const area = h.root.querySelector(`#${role}-area-management`);
    const cifBefore = cif.innerHTML, areaBefore = area.innerHTML;
    assert.equal(h.requests.some((r) => r.path === LOOKUP || r.path === REVIEW), false);
    const root = open(h);
    await setImmediate();
    assert.deepEqual(h.requests.filter((r) => [LOOKUP, REVIEW].includes(r.path)).map((r) => r.path), [LOOKUP, REVIEW]);
    assert.match(root.textContent, /Private application purpose/);
    assert.match(root.textContent, /9007199254740993\.01/);
    assert.match(root.textContent, /Private employer details/);
    assert.equal(cif.innerHTML, cifBefore);
    assert.equal(area.innerHTML, areaBefore);
    assert.equal(h.requests.some((r) => r.path.includes('/cif/review-summary')), false);
    assert.ok(h.requests.every((r) => (r.options.method ?? 'GET') === 'GET'));
  });

  test(`${role}: an unrelated or similar permission cannot expose application review`, async () => {
    const h = harness(role, [`${PERMISSION}.extra`, 'area.manage']);
    await mounts[role](h.context);
    assert.equal(h.navigation.some((item) => item.id === `${role}-application-review`), false);
    assert.equal(h.root.querySelector('[data-office-application-review]'), null);
    assert.equal(h.requests.some((r) => r.path === LOOKUP || r.path === REVIEW), false);
    h.controller.abort();
  });

  test(`${role}: workspace remount clears old selection and ignores a late application response`, async (t) => {
    const h = harness(role);
    t.after(() => h.controller.abort());
    let resolve;
    h.holdReview = new Promise((done) => { resolve = done; });
    await mounts[role](h.context);
    const old = open(h);
    await setImmediate();
    assert.equal(h.requests.filter((r) => r.path === REVIEW).length, 1);
    await mounts[role](h.context);
    resolve(summary());
    await setImmediate();
    assert.equal(old.innerHTML, '');
    assert.doesNotMatch(h.root.textContent, /Private application purpose|Private employer details/);
    assert.equal(h.root.querySelector('[data-office-application-review]').querySelector('[name="intakeReference"]').value, '');
  });

  test(`${role}: logout signal makes an in-flight application review inert`, async (t) => {
    const h = harness(role);
    t.after(() => h.controller.abort());
    let resolve;
    h.holdReview = new Promise((done) => { resolve = done; });
    await mounts[role](h.context);
    const root = open(h);
    await setImmediate();
    h.controller.abort();
    resolve(summary());
    await setImmediate();
    assert.equal(root.innerHTML, '');
    assert.doesNotMatch(h.root.textContent, /Private application purpose|Private employer details/);
  });
}
