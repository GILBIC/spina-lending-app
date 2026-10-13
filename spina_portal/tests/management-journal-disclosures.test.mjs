import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { Element, fire } from './helpers/dom.mjs';

const url = new URL('../assets/management-journal-disclosures.js', import.meta.url);
const contract = () => JSON.parse(readFileSync(new URL('./fixtures/journal-disclosures-backend.json', import.meta.url), 'utf8'));
const session = { user: { id: '00000000-0000-4000-8000-000000000001', roles: ['management'], role: 'Management' }, permissions: ['accounting.view', 'accounting.journal.manage'] };
const tick = () => new Promise(resolve => setImmediate(resolve));
async function setup({ loseResponse = false, getSession = () => session, transform = () => {}, writeError = null } = {}) {
  assert.ok(existsSync(url), 'Guided disclosure review is not implemented');
  const { mountJournalDisclosures } = await import(url);
  const value = contract(), root = new Element(), writes = [], reads = []; transform(value);
  const api = { async request(path, options = {}) {
    if (options.method === 'POST') { writes.push(structuredClone(options.body)); if (writeError) throw writeError; if (loseResponse && writes.length === 1) throw Error('Response lost'); return { review_id: options.body.request_id, policy_id: options.body.request_id }; }
    reads.push(path);
    if (path.includes('/disclosures?')) return { disclosures: value };
    return { fiscal_periods: [{ period_id: value.period.id, label: value.period.label }] };
  } };
  const dispose = await mountJournalDisclosures({ root, api, session, getSession });
  return { root, writes, reads, value, dispose };
}
function fill(root, fields) { for (const [key, value] of Object.entries(fields)) root.querySelector(`[name="${key}"]`).value = value; }

test('retained components can be reviewed and saved only after confirmation', async () => {
  const { root, writes, value, dispose } = await setup();
  fire(root.querySelector('[data-disclosure-journal]'), 'click');
  fill(root.querySelector('[data-disclosure-review]'), { reason: 'Reconfirmed borrowing contract', evidence_reference: 'Retained contract', evidence_digest: 'a'.repeat(64) });
  fire(root.querySelector('[data-disclosure-review]'), 'submit'); await tick();
  assert.equal(writes.length, 0); assert.match(root.textContent, /Reconfirmed borrowing contract/);
  fire(root.querySelector('[data-disclosure-save]'), 'click'); await tick(); await tick();
  assert.equal(writes.length, 1); assert.equal(writes[0].expected_version, value.journals[0].review_version);
  assert.equal(writes[0].source_digest, value.journals[0].source_digest); assert.equal(writes[0].reviewed, true);
  assert.deepEqual(writes[0].components, value.journals[0].components);
  dispose(); assert.equal(root.textContent, '');
});

test('lost response retries the unchanged request and blocks a new save', async () => {
  const { root, writes } = await setup({ loseResponse: true });
  fire(root.querySelector('[data-disclosure-journal]'), 'click');
  fill(root.querySelector('[data-disclosure-review]'), { reason: 'Reviewed exact source', evidence_reference: 'Contract', evidence_digest: 'a'.repeat(64) });
  fire(root.querySelector('[data-disclosure-review]'), 'submit'); await tick();
  fire(root.querySelector('[data-disclosure-save]'), 'click'); await tick(); await tick();
  assert.match(root.textContent, /Response lost/);
  fire(root.querySelector('[data-disclosure-retry]'), 'click'); await tick(); await tick();
  assert.equal(writes.length, 2); assert.deepEqual(writes[0], writes[1]);
});

test('role change clears private state before a retained button can act', async () => {
  let current = session;
  const { root, writes } = await setup({ getSession: () => current });
  const button = root.querySelector('[data-disclosure-journal]');
  current = { ...session, permissions: [] };
  fire(button, 'click'); await tick();
  assert.equal(writes.length, 0); assert.equal(root.textContent, '');
});

test('missing initial read authority never requests private accounting records', async () => {
  const { root, reads } = await setup({ getSession: () => ({ ...session, permissions: [] }) });
  assert.equal(reads.length, 0); assert.doesNotMatch(root.textContent, /Synthetic mixed acquisition/);
});

test('new mixed cash and noncash portions must cover the journal before review', async () => {
  const { root, writes, value } = await setup();
  fire(root.querySelector('[data-disclosure-journal]'), 'click');
  for (let i = 0; i < 2; i++) fire(root.querySelector('[data-disclosure-remove]'), 'click');
  fill(root.querySelector('[data-disclosure-review]'), { reason: 'Reviewed contract', evidence_reference: 'Contract', evidence_digest: 'a'.repeat(64) });
  fire(root.querySelector('[data-disclosure-review]'), 'submit'); await tick();
  assert.equal(root.querySelector('[data-disclosure-save]'), null);
  for (const part of value.journals[0].components) {
    fill(root.querySelector('[data-disclosure-part]'), part);
    fire(root.querySelector('[data-disclosure-part]'), 'submit'); await tick();
  }
  fill(root.querySelector('[data-disclosure-review]'), { reason: 'Reviewed contract', evidence_reference: 'Contract', evidence_digest: 'a'.repeat(64) });
  fire(root.querySelector('[data-disclosure-review]'), 'submit'); await tick();
  assert.equal(root.querySelector('[data-disclosure-remove]'), null);
  fire(root.querySelector('[data-disclosure-save]'), 'click'); await tick(); await tick();
  assert.deepEqual(writes[0].components, value.journals[0].components);
});

test('financing policy explicitly retains an empty selection after review', async () => {
  const { root, writes, value } = await setup();
  fire(root.querySelector('[data-disclosure-policy]'), 'click');
  const form = root.querySelector('[data-disclosure-policy-form]');
  for (const row of value.financing_account_options) form.querySelector(`[name="finance_${row.code}"]`).value = 'no';
  fill(form, { evidence_reference: 'No financing liabilities', evidence_digest: 'a'.repeat(64) });
  fire(form, 'submit'); await tick();
  assert.equal(writes.length, 0); assert.match(root.textContent, /Financing accounts: None/);
  fire(root.querySelector('[data-disclosure-save]'), 'click'); await tick(); await tick();
  assert.deepEqual(writes[0].financing_account_codes, []);
  assert.equal(writes[0].expected_version, value.policy.version);
  assert.equal(writes[0].reporting_policy_id, value.reporting_policy_id);
});

test('closed period remains readable and has no evidence editing actions', async () => {
  const { root, reads } = await setup({ transform: value => { value.period.status = 'closed'; } });
  assert.equal(reads.length, 2); assert.equal(root.querySelector('[data-disclosure-journal]'), null);
  assert.equal(root.querySelector('[data-disclosure-policy]'), null);
});

for (const status of [403, 409]) test(`server rejection ${status} cannot be shown as saved evidence`, async () => {
  const { root, writes } = await setup({ writeError: Object.assign(Error('Current review rejected'), { status }) });
  fire(root.querySelector('[data-disclosure-journal]'), 'click');
  fill(root.querySelector('[data-disclosure-review]'), { reason: 'Reviewed contract', evidence_reference: 'Contract', evidence_digest: 'a'.repeat(64) });
  fire(root.querySelector('[data-disclosure-review]'), 'submit'); await tick();
  fire(root.querySelector('[data-disclosure-save]'), 'click'); await tick(); await tick();
  assert.equal(writes.length, 1);
  if (status === 403) assert.equal(root.textContent, '');
  else { assert.match(root.textContent, /Current review rejected/); assert.ok(root.querySelector('[data-disclosure-restart]')); }
});
