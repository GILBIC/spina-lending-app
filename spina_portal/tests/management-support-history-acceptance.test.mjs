import assert from 'node:assert/strict';
import test from 'node:test';
import {Element, fire} from './helpers/dom.mjs';
import {mountManagementSupport} from '../assets/management-support.js';

const tick = () => new Promise(resolve => setImmediate(resolve));
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const session = {user: {id: 'synthetic-manager'}, permissions: ['support.manage']};
const row = (n, status = 'open') => ({
  request_id: id(n), client_id: id(n + 1000), status,
  subject: `Synthetic request ${n}`, message: `Original question ${n}`,
  reference_text: `Synthetic reference ${n}`, created_at: '2026-10-01T01:00:00Z',
  management_response: status === 'open' ? null : `Saved response ${n}`,
  responded_at: ['answered', 'resolved'].includes(status) ? '2026-10-02T01:00:00Z' : null,
  resolved_at: status === 'resolved' ? '2026-10-02T02:00:00Z' : null,
  cancelled_at: status === 'cancelled' ? '2026-10-02T03:00:00Z' : null,
});
const path = (status, offset = 0) => `/api/v1/management/support?status=${status}&limit=100&offset=${offset}`;

async function setup(t, respond) {
  const root = new Element(), calls = [];
  const handle = mountManagementSupport({root, getSession: () => session, api: {
    async request(url, options = {}) { calls.push({url, options}); return respond(url, options); },
  }});
  t.after(() => handle.dispose());
  await handle.refresh();
  return {root, calls, handle};
}

for (const status of ['answered', 'resolved', 'cancelled']) {
  test(`Support ${status} history reads its real status and exposes only authorized actions`, async t => {
    const h = await setup(t, url => ({requests: [row(url === path('open') ? 1 : 2, new URL(url, 'https://synthetic.invalid').searchParams.get('status'))]}));
    const filter = h.root.querySelector('[data-support-status]');
    assert.equal(filter.value, 'open');
    filter.value = status; fire(filter, 'change'); await tick();
    assert.deepEqual(h.calls.map(call => call.url), [path('open'), path(status)]);
    const record = h.root.querySelector(`[data-support-record="${id(2)}"]`);
    assert.ok(record);
    assert.match(record.textContent, /Original question 2/);
    assert.match(record.textContent, /Synthetic reference 2/);
    assert.match(record.textContent, /Saved response 2/);
    const form = record.querySelector('[data-support-form]');
    if (status === 'answered') {
      assert.ok(form, 'An answered request can still be resolved');
      assert.deepEqual(form.querySelectorAll('option').map(option => option.getAttribute('value')), ['resolved']);
      assert.match(record.textContent, /Answered/);
    } else {
      assert.equal(form, null, 'Closed history is read-only');
      assert.match(record.textContent, status === 'resolved' ? /Resolved/ : /Cancelled/);
    }
    assert.equal(h.calls.some(call => call.options.method), false);
  });
}

test('Support history paging preserves the status and resets the offset when that status changes', async t => {
  const h = await setup(t, url => {
    const query = new URL(url, 'https://synthetic.invalid').searchParams;
    const status = query.get('status'), offset = Number(query.get('offset'));
    return {requests: offset === 0 ? Array.from({length: 100}, (_, i) => row(i + 1, status)) : []};
  });
  const filter = h.root.querySelector('[data-support-status]');
  filter.value = 'answered'; fire(filter, 'change'); await tick();
  fire(h.root.querySelector('[data-support-next]'), 'click'); await tick();
  assert.equal(h.calls.at(-1).url, path('answered', 100));
  assert.match(h.root.textContent, /No answered support requests were returned/);
  assert.equal(h.root.querySelector('[data-support-previous]').disabled, false);
  assert.equal(h.root.querySelector('[data-support-next]').disabled, true);
  fire(h.root.querySelector('[data-support-previous]'), 'click'); await tick();
  assert.equal(h.calls.at(-1).url, path('answered'));
  assert.equal(h.root.querySelectorAll('[data-support-record]').length, 100);
  fire(h.root.querySelector('[data-support-next]'), 'click'); await tick();
  filter.value = 'resolved'; fire(filter, 'change'); await tick();
  assert.equal(h.calls.at(-1).url, path('resolved', 0));
  assert.match(h.root.querySelector('[data-support-page]').textContent, /Page 1/);
  assert.equal(h.root.querySelector('[data-support-previous]').disabled, true);
  assert.equal(h.root.querySelectorAll('[data-support-form]').length, 0);
  assert.equal(h.calls.some(call => call.options.method), false);
});

test('Support failed history page and access denial are not empty success; Refresh retries the same filter and page', async t => {
  let state = 'ready';
  const h = await setup(t, url => {
    const query = new URL(url, 'https://synthetic.invalid').searchParams;
    const status = query.get('status'), offset = Number(query.get('offset'));
    if (state === 'failed') throw Object.assign(new Error('Synthetic read unavailable'), {status: 503});
    if (state === 'denied') throw Object.assign(new Error('Synthetic access denied'), {status: 403});
    return {requests: offset ? [] : Array.from({length: 100}, (_, i) => row(i + 1, status))};
  });
  const filter = h.root.querySelector('[data-support-status]');
  filter.value = 'cancelled'; fire(filter, 'change'); await tick();
  state = 'failed'; fire(h.root.querySelector('[data-support-next]'), 'click'); await tick();
  assert.equal(h.calls.at(-1).url, path('cancelled', 100));
  assert.match(h.root.textContent, /Support could not be loaded/);
  assert.equal(h.root.querySelector('[data-management-queue-empty="support"]'), null);
  assert.equal(h.root.querySelector('[data-support-previous]').disabled, false);
  state = 'denied'; fire(h.root.querySelector('[data-support-refresh]'), 'click'); await tick();
  assert.equal(h.calls.at(-1).url, path('cancelled', 100));
  assert.match(h.root.textContent, /Synthetic access denied/);
  assert.equal(h.root.querySelector('[data-management-queue-empty="support"]'), null);
  assert.equal(h.root.querySelectorAll('[data-support-form]').length, 0);
  state = 'ready'; fire(h.root.querySelector('[data-support-refresh]'), 'click'); await tick();
  assert.equal(h.calls.at(-1).url, path('cancelled', 100));
  assert.match(h.root.textContent, /No cancelled support requests were returned/);
  assert.equal(filter.value, 'cancelled');
  assert.equal(h.calls.some(call => call.options.method), false);
});

test('resolving an answered history row preserves another draft and posts the selected filtered request ID', async t => {
  const records = [row(12, 'answered'), row(29, 'answered')];
  const h = await setup(t, (url, options) => {
    if (options.method === 'POST') return {request: {...records[1], status: 'resolved', management_response: 'Resolved synthetic case', resolved_at: '2026-10-03T01:00:00Z'}};
    return {requests: url === path('open') ? [] : records};
  });
  const filter = h.root.querySelector('[data-support-status]');
  filter.value = 'answered'; fire(filter, 'change'); await tick();
  const other = h.root.querySelector(`[data-support-record="${id(12)}"]`);
  const otherDraft = other.querySelector('[name="response"]');
  otherDraft.value = 'Unsent independent answer';
  const chosen = h.root.querySelector(`[data-support-record="${id(29)}"]`);
  const form = chosen.querySelector('[data-support-form]');
  form.querySelector('[name="action"]').value = 'resolved';
  form.querySelector('[name="response"]').value = 'Resolved synthetic case';
  fire(form, 'submit'); await tick();
  const writes = h.calls.filter(call => call.options.method);
  assert.equal(writes.length, 1);
  assert.equal(writes[0].url, `/api/v1/management/support/${id(29)}/review`);
  assert.deepEqual(writes[0].options.body, {action: 'resolved', response: 'Resolved synthetic case'});
  assert.equal(h.calls.at(-2).url, path('answered'), 'Preflight uses the active filtered page');
  assert.equal(h.root.querySelector(`[data-support-record="${id(12)}"]`), other);
  assert.equal(other.querySelector('[name="response"]'), otherDraft);
  assert.equal(otherDraft.value, 'Unsent independent answer');
  assert.equal(chosen.querySelector('[data-support-form]'), null);
  assert.match(chosen.textContent, /Response saved/);
  assert.equal(filter.value, 'answered');
});

test('Support dirty history refuses paging and status changes until deliberate discard', async t => {
  const previousConfirm = globalThis.confirm;
  let discard = false, prompts = 0;
  globalThis.confirm = () => { prompts++; return discard; };
  t.after(() => { globalThis.confirm = previousConfirm; });
  const h = await setup(t, url => ({requests: Array.from({length: 100}, (_, i) => row(i + 1, new URL(url, 'https://synthetic.invalid').searchParams.get('status')))}));
  const filter = h.root.querySelector('[data-support-status]');
  filter.value = 'answered'; fire(filter, 'change'); await tick();
  const draft = h.root.querySelector('[name="response"]');
  draft.value = 'Unsent history response';
  const before = h.calls.length;
  fire(h.root.querySelector('[data-support-next]'), 'click'); await tick();
  filter.value = 'resolved'; fire(filter, 'change'); await tick();
  assert.equal(h.calls.length, before);
  assert.equal(filter.value, 'answered');
  assert.equal(h.root.querySelector('[name="response"]'), draft);
  assert.equal(draft.value, 'Unsent history response');
  assert.equal(prompts, 2);
  discard = true;
  filter.value = 'resolved'; fire(filter, 'change'); await tick();
  assert.equal(prompts, 3);
  assert.equal(h.calls.at(-1).url, path('resolved', 0));
  assert.equal(h.root.querySelectorAll('[data-support-form]').length, 0);
  assert.equal(h.calls.some(call => call.options.method), false);
});
