import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { SpinaApi } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const APPLICANT = '11111111-1111-4111-8111-111111111111';
const CLIENT = '22222222-2222-4222-8222-222222222222';
const REFERENCE = 'Office / MiXeD Case';
const REVIEW = 'client_onboarding.requirement.review';
const VISIT = 'client_onboarding.visit.record';
const BYPASS = 'client_onboarding.bypass';
const BASE = '/api/v1/management/onboarding/applicants';
const COLLECTOR = '/api/v1/collector/onboarding/applicants';

function caseRecord() {
  return { applicant_id: APPLICANT, application_reference: REFERENCE, status: 'under_verification',
    full_name: 'Synthetic private applicant', phone_number: '00000000000', email: null,
    present_address: 'Synthetic private address', client_id: null,
    privacy_consent: true, accuracy_declaration: true, bypassed_requirements: [], bypass_reason: null,
    requirements: {
      national_id: { status: 'pending', evidence_reference: 'EXTERNAL-NATIONAL' },
      tin_id: { status: 'failed', evidence_reference: 'EXTERNAL-TIN' },
      meralco_bill: { status: 'pending', evidence_reference: 'EXTERNAL-BILL' },
      collector_visit: { status: 'pending', note: '', evidence_reference: null },
    },
  };
}
function visitProjection(record) {
  return Object.fromEntries([...['applicant_id', 'application_reference', 'status', 'full_name', 'phone_number', 'present_address'].map((key) => [key, record[key]]), ['collector_visit', record.requirements.collector_visit]]);
}
function response(payload, status = 200) { return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } }); }
function deferred() { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function harness({ role = 'employee', permissions = [REVIEW], collector = false } = {}) {
  const h = { root: new Element(), calls: [], case: caseRecord(), collector, fetch: null, controller: new AbortController() };
  h.signal = h.controller.signal;
  h.session = { user: { role }, permissions, access_token: 'synthetic-token' };
  h.api = new SpinaApi({ sessionStore: { load: () => h.session, deviceId: () => 'synthetic-device', clear() {} },
    fetchImpl(path, init) {
      h.calls.push({ path, init });
      if (h.fetch) return h.fetch(path, init);
      if (init.method === 'GET') return Promise.resolve(response(h.collector ? visitProjection(h.case) : h.case));
      const body = init.body ? JSON.parse(init.body) : null;
      if (path === BASE) {
        h.case.status = 'requirements_incomplete';
        return Promise.resolve(response({ application_reference: REFERENCE, status: h.case.status, detail: 'Office applicant intake recorded.' }, 201));
      }
      if (path.endsWith('/document-requirements')) {
        for (const name of ['national_id', 'tin_id', 'meralco_bill']) h.case.requirements[name].status = body[`${name}_status`];
      }
      if (path.endsWith('/visit')) h.case.requirements.collector_visit = { status: body.result, note: body.note, evidence_reference: body.evidence_reference };
      if (path.endsWith('/eligibility') || path.endsWith('/eligibility/bypass')) {
        h.case.status = 'eligible_for_cif'; h.case.client_id = CLIENT;
        if (body) { h.case.bypassed_requirements = body.bypassed_requirements; h.case.bypass_reason = body.reason; }
        return Promise.resolve(response({ status: h.case.status, client_id: CLIENT }));
      }
      return Promise.resolve(response({ status: h.case.status }));
    } });
  return h;
}
async function mount(h) {
  const module = h.collector ? await import('../assets/collector-onboarding-visit.js') : await import('../assets/office-onboarding.js');
  return (h.collector ? module.mountCollectorOnboardingVisit : module.mountOfficeOnboarding)(h);
}
const field = (h, name) => h.root.querySelector(`[name="${name}"]`);
const button = (h, text) => h.root.querySelectorAll('button').find((item) => item.textContent === text);
function enter(h, name, value) { field(h, name).value = value; fire(field(h, name), 'input'); }
function submit(h, selector) { assert.equal(fire(h.root.querySelector(selector), 'submit').defaultPrevented, true); }
async function open(h, reference = REFERENCE) { enter(h, 'applicationReference', reference); submit(h, '[data-case-lookup]'); await setImmediate(); }
function writeCalls(h) { return h.calls.filter(({ init }) => init.method !== 'GET'); }
function checked(h, name) { field(h, name).checked = true; fire(field(h, name), 'change'); }

for (const role of ['employee', 'management']) {
  test(`${role}: exact lookup displays truthful requirement evidence and no automatic passed decisions`, async () => {
    const h = harness({ role }); await mount(h);
    assert.equal(h.calls.length, 0);
    await open(h, ` ${REFERENCE.toLowerCase()} `);
    assert.equal(h.calls[0].path, `${BASE}/by-reference/${encodeURIComponent(REFERENCE.toLowerCase())}/case`);
    assert.equal(h.calls[0].init.headers.Authorization, 'Bearer synthetic-token');
    assert.equal(h.calls[0].init.headers['X-Device-Id'], 'synthetic-device');
    assert.equal(field(h, 'applicationReference').value, REFERENCE);
    assert.match(h.root.textContent, /Synthetic private applicant/);
    for (const evidence of ['EXTERNAL-NATIONAL', 'EXTERNAL-TIN', 'EXTERNAL-BILL']) assert.ok(h.root.textContent.includes(evidence));
    assert.match(h.root.textContent, /external evidence/i);
    for (const name of ['national_id', 'tin_id', 'meralco_bill']) assert.equal(field(h, `${name}_status`).value, '');
    assert.equal(button(h, 'Approve CIF eligibility').disabled, true);
    assert.equal(button(h, 'Approve requirement bypass'), undefined);
    assert.equal(h.root.textContent.includes(APPLICANT), false);
  });
}

test('new intake requires deliberate consent and accuracy, then sends existing strict fields and opens returned reference', async () => {
  const h = harness(); await mount(h); fire(button(h, 'New office intake'), 'click');
  assert.equal(Boolean(field(h, 'privacy_consent').checked), false);
  assert.equal(Boolean(field(h, 'accuracy_declaration').checked), false);
  const values = { full_name: 'Synthetic applicant', phone_number: '00000000000', email: '', present_address: 'Synthetic address',
    national_id_egov_evidence_reference: 'EXTERNAL-NATIONAL', tin_id_egov_evidence_reference: 'EXTERNAL-TIN', meralco_bill_evidence_reference: 'EXTERNAL-BILL' };
  for (const [name, value] of Object.entries(values)) enter(h, name, value);
  submit(h, '[data-intake-form]'); assert.equal(h.calls.length, 0);
  checked(h, 'privacy_consent'); checked(h, 'accuracy_declaration');
  const detachedName = field(h, 'full_name');
  submit(h, '[data-intake-form]'); await setImmediate();
  assert.equal(h.calls.length, 2);
  assert.deepEqual(JSON.parse(h.calls[0].init.body), { ...values, email: null, privacy_consent: true, accuracy_declaration: true });
  assert.equal(h.calls[0].path, BASE); assert.equal(h.calls[0].init.method, 'POST');
  assert.equal(h.calls[1].path, `${BASE}/by-reference/${encodeURIComponent(REFERENCE)}/case`);
  assert.equal(detachedName.value, '');
  assert.equal(field(h, 'applicationReference').value, REFERENCE);
});

test('document review and normal eligibility use the selected identity and refresh authoritative case', async () => {
  const h = harness(); h.case.requirements.collector_visit.status = 'passed'; await mount(h); await open(h);
  for (const name of ['national_id', 'tin_id', 'meralco_bill']) enter(h, `${name}_status`, 'passed');
  submit(h, '[data-document-review]'); await setImmediate();
  assert.equal(writeCalls(h)[0].path, `${BASE}/${APPLICANT}/document-requirements`);
  assert.deepEqual(JSON.parse(writeCalls(h)[0].init.body), { national_id_status: 'passed', tin_id_status: 'passed', meralco_bill_status: 'passed' });
  assert.equal(button(h, 'Approve CIF eligibility').disabled, false);
  fire(button(h, 'Approve CIF eligibility'), 'click'); await setImmediate();
  assert.equal(writeCalls(h)[1].path, `${BASE}/${APPLICANT}/eligibility`);
  assert.equal(writeCalls(h)[1].init.body, undefined);
  assert.match(h.root.textContent, /Eligible for CIF/);
  assert.equal(button(h, 'Save document review'), undefined);
  assert.equal(writeCalls(h).length, 2);
});

test('Management bypass requires exact permission, explicit full non-passed set and reason, retaining truthful failed status', async () => {
  const h = harness({ role: 'management', permissions: [REVIEW, BYPASS] });
  h.case.requirements.national_id.status = 'passed'; await mount(h); await open(h);
  assert.equal(field(h, 'bypass_national_id'), null);
  enter(h, 'bypass_reason', 'Approved exception after office review');
  checked(h, 'bypass_tin_id'); submit(h, '[data-bypass-form]'); assert.equal(writeCalls(h).length, 0);
  checked(h, 'bypass_meralco_bill'); checked(h, 'bypass_collector_visit');
  submit(h, '[data-bypass-form]'); await setImmediate();
  assert.deepEqual(JSON.parse(writeCalls(h)[0].init.body), { bypassed_requirements: ['tin_id', 'meralco_bill', 'collector_visit'], reason: 'Approved exception after office review' });
  assert.equal(writeCalls(h)[0].path, `${BASE}/${APPLICANT}/eligibility/bypass`);
  assert.equal(h.case.requirements.tin_id.status, 'failed');
  assert.match(h.root.textContent, /Approved exception after office review/);
  assert.match(h.root.textContent, /Failed/);
});

test('Employee cannot expose bypass even if accidentally granted the permission', async () => {
  const h = harness({ permissions: [REVIEW, BYPASS] }); await mount(h); await open(h);
  assert.equal(button(h, 'Approve requirement bypass'), undefined);
});

test('Collector sees only visit facts and records explicit result without any eligibility action', async () => {
  const h = harness({ role: 'collector', permissions: [VISIT], collector: true }); await mount(h); await open(h);
  assert.equal(h.calls[0].path, `${COLLECTOR}/by-reference/${encodeURIComponent(REFERENCE)}/visit-case`);
  assert.equal(button(h, 'New office intake'), undefined);
  assert.equal(button(h, 'Approve CIF eligibility'), undefined);
  assert.doesNotMatch(h.root.textContent, /EXTERNAL-NATIONAL|EXTERNAL-TIN|EXTERNAL-BILL/);
  assert.equal(field(h, 'result').value, '');
  submit(h, '[data-visit-form]'); assert.equal(writeCalls(h).length, 0);
  enter(h, 'result', 'passed'); enter(h, 'note', 'Synthetic observed residence'); enter(h, 'evidence_reference', 'EXTERNAL-VISIT');
  submit(h, '[data-visit-form]'); await setImmediate();
  assert.equal(writeCalls(h)[0].path, `${COLLECTOR}/${APPLICANT}/visit`);
  assert.deepEqual(JSON.parse(writeCalls(h)[0].init.body), { result: 'passed', note: 'Synthetic observed residence', evidence_reference: 'EXTERNAL-VISIT' });
  assert.equal(h.calls.at(-1).init.method, 'GET');
});

for (const options of [
  { role: 'collector', permissions: [REVIEW] }, { role: 'client', permissions: [REVIEW] },
  { role: 'employee', permissions: [] }, { role: 'management', permissions: [BYPASS] },
  { role: 'employee', permissions: [VISIT], collector: true }, { role: 'management', permissions: [VISIT], collector: true },
  { role: 'collector', permissions: [VISIT + '.extra'], collector: true },
]) {
  test(`role and permission isolation: ${JSON.stringify(options)}`, async () => {
    const h = harness(options); await mount(h); assert.equal(h.root.querySelector('form'), null); assert.equal(h.calls.length, 0);
  });
}

for (const status of [400, 422, 409, 500, 'network']) {
  test(`${status}: failed case mutation retains edits, blocks uncertain retry, and never automatically replays`, async () => {
    const h = harness(); await mount(h); await open(h);
    h.fetch = (_, init) => init.method === 'GET' ? Promise.resolve(response(h.case))
      : status === 'network' ? Promise.reject(new Error('Lost connection')) : Promise.resolve(response({ detail: '<img src=x> Review failed' }, status));
    for (const name of ['national_id', 'tin_id', 'meralco_bill']) enter(h, `${name}_status`, 'passed');
    submit(h, '[data-document-review]'); await setImmediate();
    assert.equal(field(h, 'tin_id_status').value, 'passed');
    assert.equal(h.root.querySelector('img'), null);
    if ([400, 422].includes(status)) assert.equal(button(h, 'Save document review').disabled, false);
    else {
      assert.equal(button(h, 'Save document review').disabled, true);
      submit(h, '[data-document-review]'); assert.equal(writeCalls(h).length, 1);
      fire(button(h, 'Reload intake case'), 'click'); await setImmediate();
      assert.equal(writeCalls(h).length, 1);
    }
  });
}

test('uncertain intake cannot submit twice or create another intake from this mounted surface', async () => {
  const h = harness(); await mount(h); fire(button(h, 'New office intake'), 'click');
  for (const name of ['full_name', 'phone_number', 'present_address', 'national_id_egov_evidence_reference', 'tin_id_egov_evidence_reference', 'meralco_bill_evidence_reference']) enter(h, name, name === 'phone_number' ? '00000000000' : 'Synthetic external fact');
  checked(h, 'privacy_consent'); checked(h, 'accuracy_declaration');
  h.fetch = () => Promise.reject(new Error('Unknown result'));
  submit(h, '[data-intake-form]'); await setImmediate();
  assert.equal(button(h, 'Record office intake').disabled, true);
  assert.equal(button(h, 'New office intake').disabled, true);
  submit(h, '[data-intake-form]'); assert.equal(writeCalls(h).length, 1);
  assert.match(h.root.textContent, /verify the office record/i);
});

for (const change of [
  (record) => { record.applicant_id = 'bad-id'; },
  (record) => { record.application_reference = 'Another reference'; },
  (record) => { record.requirements.tin_id.status = 'approved'; },
  (record) => { record.phone_number = {}; },
]) {
  test(`malformed or mismatched case fails closed: ${change.toString()}`, async () => {
    const h = harness(); change(h.case); await mount(h); await open(h);
    assert.equal(button(h, 'Save document review'), undefined);
    assert.doesNotMatch(h.root.textContent, /Synthetic private applicant/);
  });
}

for (const action of ['input', 'clear', 'abort', 'dispose', 'remount']) {
  test(`${action} removes case PII and ignores late mutation response`, async () => {
    const h = harness(); const dispose = await mount(h); await open(h);
    const pending = deferred(); h.fetch = () => pending.promise;
    for (const name of ['national_id', 'tin_id', 'meralco_bill']) enter(h, `${name}_status`, 'passed');
    const oldForm = h.root.querySelector('[data-document-review]'); const oldInput = field(h, 'tin_id_status');
    submit(h, '[data-document-review]'); submit(h, '[data-document-review]'); assert.equal(writeCalls(h).length, 1);
    if (action === 'input') enter(h, 'applicationReference', 'Other reference');
    if (action === 'clear') fire(button(h, 'Clear'), 'click');
    if (action === 'abort') h.controller.abort();
    if (action === 'dispose') dispose();
    if (action === 'remount') await mount(h);
    const markup = h.root.innerHTML; pending.resolve(response({ status: 'under_verification' })); await setImmediate();
    assert.equal(h.root.innerHTML, markup); assert.equal(oldInput.value, ''); fire(oldForm, 'submit');
    assert.equal(writeCalls(h).length, 1); assert.doesNotMatch(h.root.textContent, /Synthetic private applicant/);
  });
}

test('late case lookup cannot restore old PII after a new reference', async () => {
  const h = harness(); const pending = deferred(); h.fetch = () => pending.promise; await mount(h);
  enter(h, 'applicationReference', REFERENCE); submit(h, '[data-case-lookup]');
  enter(h, 'applicationReference', 'New reference'); pending.resolve(response(h.case)); await setImmediate();
  assert.doesNotMatch(h.root.textContent, /Synthetic private applicant/);
});

for (const status of [401, 403]) {
  test(`${status} after a write clears values and removes mutation listeners`, async () => {
    const h = harness({ role: 'collector', permissions: [VISIT], collector: true }); await mount(h); await open(h);
    enter(h, 'result', 'failed'); enter(h, 'note', 'Private note'); const oldNote = field(h, 'note');
    h.fetch = () => Promise.resolve(response({ detail: 'Access denied' }, status));
    submit(h, '[data-visit-form]'); await setImmediate();
    assert.equal(oldNote.value, ''); assert.equal(h.root.querySelector('form'), null);
    assert.doesNotMatch(h.root.textContent, /Synthetic private|Private note/);
  });
}

test('case values and external evidence references are escaped, and already-aborted mounts render nothing', async () => {
  const h = harness(); h.case.full_name = '<img src=x>'; h.case.requirements.national_id.evidence_reference = '<svg onload=x>';
  await mount(h); await open(h); assert.equal(h.root.querySelector('img'), null); assert.equal(h.root.querySelector('svg'), null);
  assert.match(h.root.innerHTML, /&lt;img/); assert.match(h.root.innerHTML, /&lt;svg/);
  h.controller.abort(); await mount(h); assert.equal(h.root.innerHTML, '');
});
