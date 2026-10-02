import assert from 'node:assert/strict';
import test from 'node:test';
import {Element, fire} from './helpers/dom.mjs';
import {mountPaymentProofs} from '../assets/payment-proofs.js';

const tick = () => new Promise(resolve => setImmediate(resolve));
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

test('Management uncertain proof review blocks read replacement and retries the exact version, review and command', async t => {
  const base = '/api/v1/management/payment-proofs';
  const version = {version_number: 2, media_type: 'image/png', note: 'Synthetic second version', uploaded_at: '2026-10-01T01:00:00Z'};
  const oldReview = {review_id: id(3), decision: 'correction_required', reason: 'First version was incomplete', reviewed_at: '2026-10-01T01:30:00Z'};
  const proof = {proof_id: id(1), loan_id: id(2), loan_number: 'SYNTHETIC-1', status: 'submitted', current_version: version, latest_review: oldReview};
  const detail = {proof, history: [
    {version: {...version, version_number: 1, note: 'Synthetic first version'}, reviews: [oldReview]},
    {version, reviews: []},
  ]};
  const root = new Element(), calls = [];
  let handle, posts = 0;
  const dispose = mountPaymentProofs({root, mode: 'management', registerHandle: value => { handle = value; }, api: {
    async request(path, options = {}) {
      calls.push({path, options});
      if (options.method === 'POST') {
        posts++;
        if (posts === 1) throw Object.assign(new Error('Synthetic response lost'), {code: 'network_uncertain'});
        const savedReview = {review_id: id(5), decision: 'correction_required', reason: 'Please include the complete reference', reviewed_at: '2026-10-03T01:00:00Z'};
        return {proof: {...proof, status: 'correction_required', latest_review: savedReview}, history: [detail.history[0], {version, reviews: [savedReview]}]};
      }
      if (path === `${base}/${id(1)}`) return detail;
      assert.equal(path, `${base}?limit=50&offset=0`);
      return {proofs: [proof, {...proof, proof_id: id(4), loan_number: 'SYNTHETIC-2'}], has_more: true};
    },
  }});
  t.after(dispose);
  await tick();
  fire(root.querySelector(`[data-proof-detail="${id(1)}"]`), 'click'); await tick();
  assert.match(root.textContent, /Version 1/);
  assert.match(root.textContent, /Version 2/);
  assert.match(root.textContent, /First version was incomplete/);
  const form = root.querySelector('[data-proof-review]');
  const reason = form.querySelector('[name="reason"]');
  form.querySelector('[name="decision"]').value = 'correction_required';
  reason.value = 'Please include the complete reference';
  fire(form, 'submit'); await tick();
  assert.equal(handle.isUncertain(), true);
  assert.match(root.textContent, /result is uncertain/);
  assert.equal(reason.disabled, true);
  assert.equal(root.querySelector('[data-proof-refresh]').disabled, true);
  assert.equal(root.querySelector('[data-proof-next]').disabled, true);
  assert.equal(form.querySelector('button[type="submit"]').disabled, false, 'Only an identical submission can be retried');
  const beforeRead = calls.length;
  await handle.refreshReadOnly();
  // Retained DOM handlers are invoked deliberately: the implementation must
  // guard them as well as showing disabled controls during uncertainty.
  fire(root.querySelector('[data-proof-refresh]'), 'click');
  fire(root.querySelector('[data-proof-next]'), 'click');
  await tick();
  assert.equal(calls.length, beforeRead, 'Read-only refresh must not clear or replace an uncertain command');
  assert.equal(handle.isUncertain(), true);
  assert.equal(root.querySelector('[data-proof-review]'), form);
  assert.equal(form.querySelector('[name="reason"]'), reason);
  assert.equal(reason.value, 'Please include the complete reference');
  fire(form, 'submit'); await tick();
  const writes = calls.filter(call => call.options.method === 'POST');
  assert.equal(writes.length, 2);
  assert.equal(writes[0].path, `${base}/${id(1)}/reviews`);
  assert.equal(writes[1].path, writes[0].path);
  assert.deepEqual(writes[1].options.body, writes[0].options.body);
  assert.match(writes[0].options.body.request_id, /^[0-9a-f-]{36}$/);
  assert.equal(writes[0].options.body.expected_version, 2);
  assert.equal(writes[0].options.body.expected_review_id, id(3));
  assert.equal(writes[0].options.body.decision, 'correction_required');
  assert.equal(writes[0].options.body.reason, 'Please include the complete reference');
  assert.equal(handle.isUncertain(), false);
  assert.match(root.textContent, /Evidence review saved. No payment was posted/);
  assert.match(root.textContent, /does not confirm settlement/);
  assert.equal(calls.filter(call => call.options.method).every(call => call.path.endsWith('/reviews')), true);
});
