import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { mountOfficeApplicationReview } from '../assets/office-application-review.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111', CIF = '22222222-2222-4222-8222-222222222222';
const APP = '33333333-3333-4333-8333-333333333333', VERSION = '44444444-4444-4444-8444-444444444444';
const EVIDENCE = '55555555-5555-4555-8555-555555555555', CONFIRM = '66666666-6666-4666-8666-666666666666';
const HASH = 'a'.repeat(64), BASE = `/api/v1/management/clients/${CLIENT}`;
function review() { return { client_id: CLIENT, cif_version_id: CIF, application_id: APP, application_version_id: VERSION,
  application_reference: 'App-1', cif_version_number: 1, version_number: 1, requested_loan_type_name: null,
  recorded_at: '2026-09-19T01:02:03Z', review_scope: 'loan_application_information_only', missing_fields: [],
  information: { request: { requested_loan_type_id: EVIDENCE, purpose: 'Synthetic loan', requested_amount: '1000.00', requested_payment_arrangement: 'Weekly', requested_term: 'Ten weeks', preferred_first_payment_date: null },
    repayment: { repayment_source: 'Employment', source_details: 'Synthetic details', monthly_gross_income: '10000', monthly_net_income: '9000', has_existing_obligations: false, obligations: [] } } }; }
function context() { return { client_id: CLIENT, cif_version_id: CIF, application_id: APP, application_version_id: VERSION,
  purpose: 'application_review', snapshot_sha256: HASH, issuance_ready: true }; }
function capture() { return { ...context(), evidence_id: EVIDENCE, evidence_reference: `office-evidence:${EVIDENCE}` }; }
function confirmation() { return { client_id: CLIENT, cif_version_id: CIF, application_id: APP, application_version_id: VERSION,
  review_confirmation_id: CONFIRM, confirmed_at: '2026-09-19T01:02:03Z', review_scope: 'loan_application_information_only' }; }
function field(h, name) { return h.root.querySelector(`[name="${name}"]`); }
function button(h, attr) { return h.root.querySelector(`[data-${attr}]`); }
function click(h, attr) { fire(button(h, attr), 'click'); }
function harness() {
  const h = { root: new Element(), session: { user: { role: 'employee' }, permissions: ['client_onboarding.requirement.review'] },
    controller: new AbortController(), calls: [], response: null, saved: review() };
  h.signal = h.controller.signal;
  h.api = { async request(path, options = {}) {
    h.calls.push({ path, ...options });
    if (h.response) return h.response(path, options);
    if (path.endsWith('/cif-client')) return { client_id: CLIENT, application_reference: 'Intake-1' };
    if (path.endsWith('/review-summary')) return h.saved;
    if (path.includes('/review-evidence/context')) return context();
    if (path.includes('/review-evidence?')) return capture();
    if (path.endsWith('/review-confirmations')) return confirmation();
    throw new Error(`Unexpected request ${path}`);
  } };
  h.dispose = mountOfficeApplicationReview(h);
  return h;
}
async function open(h) { field(h, 'intakeReference').value = 'Intake-1'; field(h, 'applicationReference').value = 'App-1'; fire(h.root.querySelector('form'), 'submit'); await setImmediate(); }
async function prepare(h) { click(h, 'prepare-application-confirmation'); await setImmediate(); }
async function captureSigned(h) {
  field(h, 'signedScan').files = [new Blob(['%PDF-1.7\nSynthetic signed review'], { type: 'application/pdf' })];
  field(h, 'signedScan').value = 'signed.pdf'; field(h, 'witnessed').checked = true;
  fire(button(h, 'application-signed-evidence').querySelector('form'), 'submit'); await setImmediate();
}

test('review remains two GETs until staff prepares exact signed evidence, then one explicit confirmation', async () => {
  const h = harness(); await open(h); assert.equal(h.calls.length, 2);
  await prepare(h); const source = new URL(h.calls[2].path, 'https://office.example').searchParams;
  assert.equal(source.get('purpose'), 'application_review'); assert.equal(source.get('cif_version_id'), CIF);
  assert.equal(source.get('application_id'), APP); assert.equal(source.get('application_version_id'), VERSION);
  assert.equal(button(h, 'confirm-application').disabled, true);
  click(h, 'confirm-application'); assert.equal(h.calls.length, 3);
  await captureSigned(h); assert.equal(h.calls.length, 4); assert.equal(button(h, 'confirm-application').disabled, false);
  click(h, 'confirm-application'); click(h, 'confirm-application'); await setImmediate();
  assert.equal(h.calls.length, 5); assert.equal(h.calls[4].path, `${BASE}/loan-applications/${APP}/review-confirmations`);
  assert.deepEqual(h.calls[4].body, { application_version_id: VERSION, applicant_confirmation_evidence_reference: `office-evidence:${EVIDENCE}` });
  assert.match(h.root.textContent, /Applicant application review confirmed/);
  assert.match(h.root.textContent, /Approval, final loan signing, and release remain separate/);
  click(h, 'confirm-application'); assert.equal(h.calls.length, 5); h.dispose();
});

test('incomplete request or repayment facts cannot prepare applicant confirmation', async () => {
  const h = harness(); h.saved.missing_fields = ['request.purpose']; await open(h);
  assert.equal(button(h, 'prepare-application-confirmation').disabled, true);
  click(h, 'prepare-application-confirmation'); await setImmediate(); assert.equal(h.calls.length, 2); h.dispose();
});

for (const action of ['input', 'clear', 'edit', 'abort', 'dispose', 'remount']) test(`${action} invalidates a pending signed capture and detached confirmation button`, async () => {
  const h = harness(); await open(h); await prepare(h); let resolve;
  h.response = (path) => path.endsWith('/entry-context') ? {} : new Promise(done => { resolve = done; });
  await captureSigned(h); const confirmButton = button(h, 'confirm-application'); const scan = field(h, 'signedScan');
  if (action === 'input') fire(field(h, 'applicationReference'), 'input');
  if (action === 'clear') fire(h.root.querySelector('button[type="button"]'), 'click');
  if (action === 'edit') click(h, 'edit-application');
  if (action === 'abort') h.controller.abort();
  if (action === 'dispose') h.dispose();
  if (action === 'remount') mountOfficeApplicationReview(h);
  resolve(capture()); await setImmediate(); fire(confirmButton, 'click'); await setImmediate();
  assert.equal(scan.value, '');
  assert.equal(h.calls.some(call => call.path.endsWith('/review-confirmations')), false); h.dispose();
});

for (const failure of [409, 503, 'network_uncertain', 'mismatched-success']) test(`${failure} confirmation requires reload and never retries blindly`, async () => {
  const h = harness(); await open(h); await prepare(h); await captureSigned(h);
  h.response = () => {
    if (failure === 'mismatched-success') return { ...confirmation(), application_version_id: CIF };
    throw Object.assign(new Error('Synthetic confirmation error'), typeof failure === 'number' ? { status: failure } : { code: failure });
  };
  click(h, 'confirm-application'); await setImmediate(); click(h, 'confirm-application'); await setImmediate();
  assert.equal(h.calls.filter(call => call.path.endsWith('/review-confirmations')).length, 1);
  assert.match(h.root.textContent, /Open the application review again/);
  assert.doesNotMatch(h.root.textContent, /Applicant application review confirmed/);
  assert.equal(button(h, 'application-signed-evidence').innerHTML, ''); h.dispose();
});

test('validation error keeps captured exact evidence for an intentional retry', async () => {
  const h = harness(); await open(h); await prepare(h); await captureSigned(h);
  h.response = () => { throw Object.assign(new Error('Synthetic validation error'), { status: 422 }); };
  click(h, 'confirm-application'); await setImmediate(); assert.equal(button(h, 'confirm-application').disabled, false);
  h.response = () => confirmation(); click(h, 'confirm-application'); await setImmediate();
  assert.match(h.root.textContent, /Applicant application review confirmed/); h.dispose();
});

test('denied confirmation clears all selected facts and references', async () => {
  const h = harness(); await open(h); await prepare(h); await captureSigned(h); const input = field(h, 'intakeReference');
  h.response = () => { throw Object.assign(new Error('Denied'), { status: 403 }); };
  click(h, 'confirm-application'); await setImmediate(); assert.equal(h.root.innerHTML, ''); assert.equal(input.value, '');
});

test('late confirmation after selection changes cannot restore a success or private information', async () => {
  const h = harness(); await open(h); await prepare(h); await captureSigned(h); let resolve;
  h.response = () => new Promise(done => { resolve = done; }); click(h, 'confirm-application');
  fire(field(h, 'intakeReference'), 'input'); resolve(confirmation()); await setImmediate();
  assert.doesNotMatch(h.root.textContent, /Synthetic loan|Applicant application review confirmed/); h.dispose();
});

function printContext(saved = review()) { return { ...context(), review_snapshot: {
  schema_version: 1, scope: 'application_information_review', client_id: CLIENT, cif_version_id: CIF,
  application_id: APP, application_version_id: VERSION, information: saved.information,
  cif_information: { full_name: 'Synthetic linked CIF <img src=x>', phone_number: '00000000000', email: null,
    present_address: 'Saved CIF address', identity_information: { birth_date: '1990-01-02', birth_place: 'Synthetic town', civil_status: null, citizenship: 'Declared citizenship' } },
} }; }
function printDocument(t) {
  const original = globalThis.document, frames = [], printed = [];
  globalThis.document = { body: { appendChild(frame) { frames.push(frame); } }, createElement(tag) {
    assert.equal(tag, 'iframe'); const frame = { style: {}, setAttribute() {}, remove() { this.removed = true; } };
    frame.contentWindow = { focus() {}, print() { printed.push(frame.srcdoc); } }; return frame;
  } };
  t.after(() => { globalThis.document = original; }); return { frames, printed };
}

test('print uses exact attached CIF/application snapshot and clears the isolated copy after printing', async (t) => {
  const document = printDocument(t), h = harness(); await open(h);
  h.response = () => printContext(); click(h, 'print-application'); await setImmediate();
  assert.equal(h.calls.length, 3); assert.ok(h.calls[2].path.includes('/review-evidence/context?'));
  assert.equal(document.frames.length, 1); const frame = document.frames[0];
  frame.onload(); assert.equal(document.printed.length, 1);
  const html = document.printed[0];
  assert.match(html, /Synthetic linked CIF &lt;img src=x&gt;/); assert.match(html, /Saved CIF address/);
  assert.match(html, /Declared citizenship/); assert.match(html, /Synthetic loan/); assert.match(html, /PHP 1000\.00/);
  assert.ok(!html.includes(CLIENT) && !html.includes(CIF)); assert.match(html, /default-src 'none'/);
  assert.equal(frame.srcdoc, ''); assert.equal(frame.removed, true); h.dispose();
});

for (const mismatch of ['application', 'CIF', 'facts']) test(`print fails closed for mismatched ${mismatch}`, async (t) => {
  const document = printDocument(t), h = harness(); await open(h); const value = printContext();
  if (mismatch === 'application') value.review_snapshot.application_version_id = CIF;
  if (mismatch === 'CIF') value.cif_version_id = APP;
  if (mismatch === 'facts') value.review_snapshot.information.request.requested_amount = 'changed';
  h.response = () => value; click(h, 'print-application'); await setImmediate();
  assert.equal(document.frames.length, 0); assert.match(h.root.textContent, /does not match/); h.dispose();
});

test('selection changes invalidate late print context and clear an unprinted detached copy', async (t) => {
  const document = printDocument(t), h = harness(); await open(h); let resolve;
  h.response = () => new Promise(done => { resolve = done; }); click(h, 'print-application');
  fire(field(h, 'intakeReference'), 'input'); resolve(printContext()); await setImmediate();
  assert.equal(document.frames.length, 0);
  h.response = null; await open(h); h.response = () => printContext(); click(h, 'print-application'); await setImmediate();
  const frame = document.frames[0], load = frame.onload; h.controller.abort(); load();
  assert.equal(frame.removed, true); assert.equal(frame.srcdoc, ''); assert.deepEqual(document.printed, []);
});
