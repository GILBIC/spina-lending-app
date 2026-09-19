import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { mountOfficeApplicationEntry } from '../assets/office-application-entry.js';
import { mountOfficeApplicationReview } from '../assets/office-application-review.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111';
const APPLICATION = '22222222-2222-4222-8222-222222222222';
const VERSION = '33333333-3333-4333-8333-333333333333';
const CIF = '44444444-4444-4444-8444-444444444444';
const NEXT = '55555555-5555-4555-8555-555555555555';
const session = { user: { role: 'employee' }, permissions: ['client_onboarding.requirement.review'] };
function details() {
  return { schema_version: 1, employment: {
    employer_or_business_name: 'Synthetic shop', position_or_business_nature: 'Retail',
    length_of_employment_or_operation: 'Two years', employer_or_business_address: 'Synthetic address', contact_number: '00000000000',
  }, references: [{ full_name: 'Synthetic contact', relationship: 'Sibling', phone_number: '00000000001', address: 'Synthetic contact address' }] };
}
function information(extra = true) {
  return { request: { requested_loan_type_id: null, purpose: null, requested_amount: '9007199254740993.01', requested_payment_arrangement: null, requested_term: null, preferred_first_payment_date: null },
    repayment: { repayment_source: null, source_details: null, monthly_gross_income: null, monthly_net_income: null, has_existing_obligations: null, obligations: [] },
    ...(extra ? { details: details() } : {}) };
}
function review(extra = true) {
  return { client_id: CLIENT, application_id: APPLICATION, application_version_id: VERSION, application_reference: 'App-Exact', cif_version_id: CIF, cif_version_number: 3,
    version_number: 4, information: information(extra), missing_fields: [], recorded_at: '2026-09-19T01:02:03Z', review_scope: 'loan_application_information_only', requested_loan_type_name: null };
}
function harness({ saved = null, response } = {}) {
  const h = { root: new Element(), session, clientId: CLIENT, applicationReference: 'App-Exact', review: saved,
    controller: new AbortController(), calls: [], saved: [] };
  h.signal = h.controller.signal;
  h.onSaved = (value) => h.saved.push(value);
  h.api = { async request(path, options = {}) {
    h.calls.push({ path, ...options });
    if (response) return response(path, options);
    if (path.endsWith('entry-context')) return { client_id: CLIENT, cif_version_id: CIF, cif_version_number: 3, loan_types: [] };
    return { ...review(), application_version_id: NEXT, version_number: saved ? 5 : 1, information: options.body.information };
  } };
  return h;
}
function field(h, name) { return h.root.querySelector(`[name="${name}"]`); }
function button(h, text) { return h.root.querySelectorAll('button').find((item) => item.textContent === text); }
function submit(h) { fire(h.root.querySelector('form'), 'submit'); }
async function openReview(saved) {
  const h = harness({ response: async (path) => path.endsWith('/cif-client') ? { client_id: CLIENT, application_reference: 'Intake-1' } : saved });
  mountOfficeApplicationReview(h);
  field(h, 'intakeReference').value = 'Intake-1';
  field(h, 'applicationReference').value = 'App-Exact';
  submit(h); await setImmediate();
  return h;
}

test('legacy draft keeps its two-section body when optional employment and references are blank', async () => {
  const h = harness(); mountOfficeApplicationEntry(h); await setImmediate();
  assert.ok(field(h, 'employer_or_business_name'));
  assert.match(h.root.textContent, /optional/i);
  submit(h); await setImmediate();
  assert.deepEqual(Object.keys(h.calls.at(-1).body.information), ['request', 'repayment']);
  assert.equal(h.saved.length, 1);
});

test('create records all optional declared facts and multiple references with exact money text', async () => {
  const h = harness(); mountOfficeApplicationEntry(h); await setImmediate();
  for (const [name, value] of Object.entries(details().employment)) field(h, name).value = value;
  field(h, 'requested_amount').value = '9007199254740993.01';
  for (let index = 0; index < 4; index += 1) {
    fire(button(h, 'Add reference'), 'click');
    for (const [name, value] of Object.entries(details().references[0])) field(h, `reference_${index}_${name}`).value = value;
  }
  submit(h); await setImmediate();
  const body = h.calls.at(-1).body;
  assert.equal(body.information.request.requested_amount, '9007199254740993.01');
  assert.deepEqual(body.information.details, { ...details(), references: Array.from({ length: 4 }, () => details().references[0]) });
  assert.equal(h.saved.length, 1);
});

test('append prefills saved optional facts; obligation and reference changes preserve other edits', async () => {
  const h = harness({ saved: review() }); mountOfficeApplicationEntry(h); await setImmediate();
  assert.equal(field(h, 'employer_or_business_name').value, 'Synthetic shop');
  assert.equal(field(h, 'reference_0_relationship').value, 'Sibling');
  field(h, 'position_or_business_nature').value = 'Updated trade';
  fire(button(h, 'Add obligation'), 'click');
  field(h, 'obligation_0_creditor').value = 'Synthetic creditor';
  fire(button(h, 'Add reference'), 'click');
  assert.equal(field(h, 'obligation_0_creditor').value, 'Synthetic creditor');
  assert.equal(field(h, 'position_or_business_nature').value, 'Updated trade');
  fire(button(h, 'Remove reference 1'), 'click');
  field(h, 'reference_0_full_name').value = 'Replacement contact';
  submit(h); await setImmediate();
  assert.equal(h.calls.at(-1).body.expected_version_number, 4);
  assert.equal(h.calls.at(-1).body.information.details.references[0].full_name, 'Replacement contact');
  assert.equal(h.saved.length, 1);
});

test('clearing an existing details snapshot persists explicit empty optional sections', async () => {
  const h = harness({ saved: review() }); mountOfficeApplicationEntry(h); await setImmediate();
  for (const name of Object.keys(details().employment)) field(h, name).value = '  ';
  fire(button(h, 'Remove reference 1'), 'click');
  submit(h); await setImmediate();
  const extra = h.calls.at(-1).body.information.details;
  assert.equal(extra.schema_version, 1);
  assert.ok(Object.values(extra.employment).every((value) => value === null));
  assert.deepEqual(extra.references, []);
});

test('review renders saved optional facts, all reference rows and escaped content without current CIF reads', async () => {
  const saved = review(); saved.information.details.references.push({ full_name: '<img src=x onerror=alert(1)>', relationship: null, phone_number: null, address: null });
  const h = await openReview(saved);
  for (const value of Object.values(details().employment)) assert.ok(h.root.textContent.includes(value));
  assert.ok(h.root.textContent.includes('Synthetic contact address'));
  assert.match(h.root.innerHTML, /&lt;img/);
  assert.equal(h.root.querySelector('img'), null);
  assert.match(h.root.textContent, /Reference 2/);
  assert.match(h.root.textContent, /Not provided/);
  assert.match(h.root.textContent, /PHP 9007199254740993\.01/);
  assert.equal(h.calls.length, 2);
  assert.ok(h.calls.every((call) => !call.method));
});

test('legacy review identifies that optional details were not recorded in that saved version', async () => {
  const h = await openReview(review(false));
  assert.match(h.root.textContent, /Employment and reference details were not recorded in this saved version/);
});

for (const mutate of [
  (value) => { value.schema_version = '1'; },
  (value) => { value.employment.contact_number = 123; },
  (value) => { value.references[0].relationship = false; },
  (value) => { value.references = {}; },
  (value) => { value.verified = true; },
]) {
  test(`unexpected optional details fail closed: ${mutate}`, async () => {
    const saved = review(); mutate(saved.information.details);
    const h = await openReview(saved);
    assert.match(h.root.textContent, /invalid/);
    assert.ok(!h.root.textContent.includes('Synthetic shop'));
    const entry = harness({ saved }); mountOfficeApplicationEntry(entry); await setImmediate();
    assert.equal(entry.calls.length, 0);
    assert.equal(entry.root.querySelector('form'), null);
  });
}

test('aborting editor clears detached employment and reference values and suppresses late save callbacks', async () => {
  let resolve;
  const h = harness({ saved: review(), response: (path) => path.endsWith('entry-context')
    ? { client_id: CLIENT, cif_version_id: CIF, cif_version_number: 3, loan_types: [] }
    : new Promise((yes) => { resolve = yes; }) });
  mountOfficeApplicationEntry(h); await setImmediate();
  const employment = field(h, 'employer_or_business_name');
  const contact = field(h, 'reference_0_full_name');
  submit(h); h.controller.abort();
  assert.equal(employment.value, ''); assert.equal(contact.value, '');
  resolve({ ...review(), version_number: 5, application_version_id: NEXT }); await setImmediate();
  assert.deepEqual(h.saved, []); assert.equal(h.root.innerHTML, '');
});
