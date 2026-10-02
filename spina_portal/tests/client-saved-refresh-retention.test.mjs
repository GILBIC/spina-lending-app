import test from 'node:test';
import assert from 'node:assert/strict';
import {Element, fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';

const tick = () => new Promise(resolve => setImmediate(resolve));
const clientId = '50000000-0000-4000-8000-000000000001';
const loanId = '60000000-0000-4000-8000-000000000001';
const otherLoanId = '60000000-0000-4000-8000-000000000002';
const requestId = '40000000-0000-4000-8000-000000000001';
const signerId = '70000000-0000-4000-8000-000000000001';
const stamp = '2026-10-02T01:00:00Z';
const approved = {request_id:requestId, client_id:clientId, loan_id:loanId,
  status:'approved', requested_amount:'5000.00', approved_principal:'5000.00',
  renewal_offset_amount:'100.00', net_release_amount:'4900.00', amount_locked_at:stamp};

async function harness(t, {record, mutation = () => ({})} = {}) {
  const prior = {FormData:globalThis.FormData, document:globalThis.document,
    confirm:globalThis.confirm, setTimeout:globalThis.setTimeout};
  const toasts = [];
  globalThis.FormData = class {
    constructor(form) { this.form = form; }
    get(name) { return this.form.querySelector(`[name="${name}"]`)?.value; }
  };
  globalThis.document = {getElementById:() => ({append:toast => toasts.push(toast.textContent)}),
    createElement:() => ({remove() {}})};
  globalThis.confirm = () => true;
  globalThis.setTimeout = () => ({unref() {}});
  t.after(() => Object.assign(globalThis, prior));
  const root = new Element();
  const query = root.querySelectorAll.bind(root);
  root.querySelectorAll = selector => {
    const pair = selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);
    return pair ? query(pair[1]).filter(node => node.getAttribute(pair[2].slice(1,-1)) !== null) : query(selector);
  };
  const controller = new AbortController();
  t.after(() => controller.abort());
  const calls = [];
  let handle, failedRead = null, failedStatus = 503;
  let loans = [{loan_id:loanId, loan_number:'SYNTHETIC-ONE', eligible:true}];
  const api = {request:async (path, options = {}) => {
    calls.push({path, options});
    if (options.method) return mutation(path, options);
    if (path.endsWith(failedRead || '/never')) throw Object.assign(Error('Protected read unavailable'), {status:failedStatus});
    if (path.endsWith('/loans')) return {client:{client_id:clientId}, loans:[]};
    if (path.endsWith('/renewals')) return {client:{client_id:clientId}, loans, requests:record ? [record] : []};
    if (path.endsWith('/renewal-workflow')) return {requests:record ? [record] : []};
    if (path.includes('/payment-proofs')) return {proofs:[], capability:{upload_available:true, max_bytes:10485760}};
    if (path.endsWith('/payments')) return {payments:[]};
    if (path.endsWith('/activity-notifications')) return [];
    if (path.endsWith('/account')) return {profile:{}};
    return {client:{client_id:clientId}, requests:[]};
  }};
  const session = {user:{id:'synthetic-owner', role:'Client'}};
  const context = {root, api, session, getSession:() => session, signal:controller.signal,
    setNavigation() {}, registerWorkspaceHandle:value => handle = value};
  await mountClientWorkspace(context);
  await handle.activate('client-renewals');
  await handle.activate('client-support');
  await handle.activate('client-payment-proofs');
  await tick();
  await tick();
  return {root, context, handle, controller, session, calls, toasts,
    failRead:(path, status = 503) => {failedRead = path; failedStatus = status;},
    setLoans:value => loans = value};
}

function drafts(h) {
  const renewal = h.root.querySelector('#client-renewal-form');
  const support = h.root.querySelector('#client-support-form');
  const file = h.root.querySelector('[name="proofFile"]');
  const selected = new Blob(['synthetic PNG bytes'], {type:'image/png'});
  file.files = [selected];
  file.value = 'synthetic.png';
  renewal.querySelector('[name="loanId"]').value = loanId;
  renewal.querySelector('[name="requestedAmount"]').value = '5000';
  renewal.querySelector('[name="message"]').value = 'Private renewal draft';
  support.querySelector('[name="category"]').value = 'payment';
  support.querySelector('[name="subject"]').value = 'Private question';
  support.querySelector('[name="referenceText"]').value = 'Private reference';
  support.querySelector('[name="message"]').value = 'Private Support draft';
  h.root.querySelector('[name="note"]').value = 'Private proof note';
  return {renewal, support, file, selected};
}

function assertSiblingDrafts(h, held) {
  assert.equal(h.root.querySelector('#client-renewal-form'), held.renewal);
  assert.equal(h.root.querySelector('#client-support-form'), held.support);
  assert.equal(h.root.querySelector('[name="proofFile"]'), held.file);
  assert.equal(held.file.files[0], held.selected);
  assert.equal(held.renewal.querySelector('[name="requestedAmount"]').value, '5000');
  assert.equal(held.renewal.querySelector('[name="message"]').value, 'Private renewal draft');
  assert.equal(held.support.querySelector('[name="message"]').value, 'Private Support draft');
  assert.equal(h.root.querySelector('[name="note"]').value, 'Private proof note');
}

const actions = [
  {name:'cancel', selector:'[data-client-renewal-cancel]', record:{...approved, status:'pending'},
    saved:record => ({...record, status:'cancelled'})},
  {name:'accept', selector:'[data-client-renewal-decision="accepted"]', record:approved,
    saved:record => ({...record, client_decision:'accepted'})},
  {name:'decline', selector:'[data-client-renewal-decision="declined"]', record:approved,
    saved:record => ({...record, client_decision:'declined'})},
  {name:'sign', selector:'[data-client-renewal-sign-request]', record:{...approved,
    client_decision:'accepted', office_processing_required:false, signer_readiness_status:'ready',
    signers:[{signer_id:signerId, party_role:'borrower', has_app:true, government_id_verified:true, selfie_verified:true, signed:false}]},
    saved:record => ({...record, signers:record.signers.map(signer => ({...signer, signed:true}))})},
  {name:'cash', selector:'[data-client-renewal-cash-confirm]', record:{...approved, cash_given_to_client_at:stamp},
    saved:record => ({...record, client_cash_confirmed_at:stamp})},
];

for (const action of actions) for (const failedRead of ['/renewals', '/renewal-workflow']) {
  test(`${action.name}: verified save reports ${failedRead} read failure without resetting drafts or retrying POST`, async t => {
    const h = await harness(t, {record:action.record, mutation:() => ({request:action.saved(action.record)})});
    const held = drafts(h);
    const button = h.root.querySelector(action.selector);
    assert.ok(button, 'the real workflow offers this action');
    h.failRead(failedRead);
    fire(button, 'click');
    await tick(); await tick();
    assertSiblingDrafts(h, held);
    assert.match(h.toasts.at(-1) || '', /Saved; refreshing records failed/);
    const postIndex = h.calls.findIndex(call => call.options.method === 'POST');
    assert.deepEqual(h.calls.slice(postIndex + 1).map(call => call.path),
      ['/api/v1/client/renewals', '/api/v1/client/renewal-workflow']);
    h.failRead(null);
    await h.context.clientLoad('renewals', {refresh:true});
    await h.context.clientLoad('renewalWorkflow', {refresh:true});
    const repeated = h.root.querySelector(action.selector);
    assert.equal(repeated.disabled, true);
    repeated.disabled = false;
    fire(repeated, 'click');
    await tick();
    assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 1);
  });
}

for (const action of actions) test(`${action.name}: accepted late response keeps detached controls disabled after scope loss`, async t => {
  let resolve;
  const h = await harness(t, {record:action.record, mutation:() => new Promise(done => resolve = done)});
  const held = drafts(h);
  const button = h.root.querySelector(action.selector);
  fire(button, 'click');
  await tick();
  h.controller.abort();
  const callsAtAbort = h.calls.length;
  resolve({request:action.saved(action.record)});
  await tick(); await tick();
  assert.equal(button.disabled, true, 'a stale completion must not restore an old control');
  assert.equal(held.support.querySelector('[name="message"]').value, '');
  assert.equal(held.renewal.querySelector('[name="message"]').value, '');
  assert.equal(h.root.innerHTML, '');
  assert.equal(h.calls.length, callsAtAbort);
  assert.deepEqual(h.toasts, []);
});

test('creation reports a failed second refresh while preserving later typing and sibling File', async t => {
  let resolve, submitted;
  const h = await harness(t, {mutation:(_path, options) => {
    submitted = options.body;
    return new Promise(done => resolve = done);
  }});
  const held = drafts(h);
  held.renewal.querySelector('button[type="submit"]').disabled = false;
  fire(held.renewal, 'submit');
  await tick();
  held.renewal.querySelector('[name="requestedAmount"]').value = '6000';
  held.renewal.querySelector('[name="message"]').value = 'Later renewal typing';
  h.failRead('/renewal-workflow');
  resolve({request:{request_id:requestId, client_id:clientId, loan_id:loanId, status:'pending',
    submitted_at:stamp, requested_amount:'5000.00', client_message:submitted.message}});
  await tick(); await tick();
  assert.equal(h.root.querySelector('#client-renewal-form'), held.renewal);
  assert.equal(held.renewal.querySelector('[name="requestedAmount"]').value, '6000');
  assert.equal(held.renewal.querySelector('[name="message"]').value, 'Later renewal typing');
  assert.equal(held.support.querySelector('[name="message"]').value, 'Private Support draft');
  assert.equal(h.root.querySelector('[name="proofFile"]'), held.file);
  assert.equal(held.file.files[0], held.selected);
  assert.match(h.toasts.at(-1) || '', /Saved; refreshing records failed/);
  held.renewal.querySelector('button[type="submit"]').disabled = false;
  fire(held.renewal, 'submit');
  await tick();
  assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 1);
});

for (const loss of ['abort', 'authority', 'read401', 'read403', 'support401', 'support403', 'renewal401', 'renewal403']) {
  test(`${loss}: scope loss clears and disables retained private fields before panel removal`, async t => {
    const status = Number(loss.slice(-3));
    const h = await harness(t, {mutation:() => {throw Object.assign(Error('Access denied'), {status});}});
    const held = drafts(h);
    const privateFields = [...held.support.querySelectorAll('input'), ...held.support.querySelectorAll('textarea'),
      ...held.support.querySelectorAll('select'), ...held.renewal.querySelectorAll('input'),
      ...held.renewal.querySelectorAll('textarea'), ...held.renewal.querySelectorAll('select'),
      held.file, h.root.querySelector('[name="note"]')];
    const buttons = [held.support.querySelector('button[type="submit"]'), held.renewal.querySelector('button[type="submit"]')];
    if (loss === 'abort') h.controller.abort();
    else if (loss === 'authority') {h.session.user.id = 'replacement-owner'; await h.handle.refreshVisible();}
    else if (loss.startsWith('read')) {h.failRead('/support', status); await h.context.clientLoad('support', {refresh:true});}
    else {
      const form = loss.startsWith('support') ? held.support : held.renewal;
      form.querySelector('button[type="submit"]').disabled = false;
      fire(form, 'submit');
      await tick(); await tick();
    }
    assert.equal(h.root.innerHTML, '');
    for (const field of privateFields) {
      assert.equal(field.value, '', `retained ${field.getAttribute('name')} must be cleared`);
      assert.equal(field.disabled, true, `retained ${field.getAttribute('name')} must be inert`);
    }
    for (const button of buttons) assert.equal(button.disabled, true);
    const postsBefore = h.calls.filter(call => call.options.method === 'POST').length;
    // A stale event cannot rely on cached button state to regain authority.
    for (const button of buttons) button.disabled = false;
    fire(held.support, 'submit'); fire(held.renewal, 'submit');
    await tick();
    assert.equal(h.calls.filter(call => call.options.method === 'POST').length, postsBefore);
  });
}

test('a late verified Support response cannot restore fields or read after abort', async t => {
  let resolve, submitted;
  const h = await harness(t, {mutation:(_path, options) => {
    submitted = options.body;
    return new Promise(done => resolve = done);
  }});
  const held = drafts(h);
  fire(held.support, 'submit');
  await tick();
  h.controller.abort();
  const callsAtAbort = h.calls.length;
  resolve({request:{...submitted, request_id:requestId, client_id:clientId, status:'open', created_at:stamp}});
  await tick(); await tick();
  assert.equal(held.support.querySelector('[name="message"]').value, '');
  assert.equal(held.renewal.querySelector('[name="message"]').value, '');
  assert.equal(held.file.value, '');
  assert.equal(h.root.innerHTML, '');
  assert.equal(h.calls.length, callsAtAbort);
  assert.deepEqual(h.toasts, []);
});

// Model the native select behavior missing from the lightweight DOM fixture:
// replacing options resets the selection, and an absent value becomes empty.
function nativeSelect(select) {
  const html = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  let selected = select.value;
  Object.defineProperties(select, {
    innerHTML:{get:() => html.get.call(select), set:value => {
      html.set.call(select, value);
      selected = select.querySelector('option')?.getAttribute('value') || '';
    }},
    value:{get:() => selected, set:value => {
      selected = select.querySelectorAll('option').some(option => option.getAttribute('value') === value) ? value : '';
    }},
  });
}

test('renewal selection survives loading, failure and reordered recovery; missing loan requires explicit replacement', async t => {
  const h = await harness(t);
  const held = drafts(h);
  const select = held.renewal.querySelector('[name="loanId"]');
  const submit = held.renewal.querySelector('button[type="submit"]');
  nativeSelect(select);
  const first = {loan_id:loanId, loan_number:'SYNTHETIC-ONE', eligible:true};
  const second = {loan_id:otherLoanId, loan_number:'SYNTHETIC-TWO', eligible:true};
  h.setLoans([first, second]);
  await h.context.clientLoad('renewals', {refresh:true});
  select.value = otherLoanId; fire(select, 'change');
  h.failRead('/renewals');
  const failed = h.context.clientLoad('renewals', {refresh:true});
  assert.equal(select.value, otherLoanId, 'loading must not silently forget the selected loan');
  assert.equal(submit.disabled, true);
  await failed;
  assert.equal(select.value, otherLoanId);
  assert.equal(submit.disabled, true);
  h.failRead(null); h.setLoans([second, first]);
  await h.context.clientLoad('renewals', {refresh:true});
  h.setLoans([first, second]);
  await h.context.clientLoad('renewals', {refresh:true});
  assert.equal(select.value, otherLoanId, 'reordered reads must preserve the selected identifier');
  assert.equal(submit.disabled, false);
  h.setLoans([first]);
  await h.context.clientLoad('renewals', {refresh:true});
  assert.notEqual(select.value, loanId, 'invalidated eligibility must not retarget the draft');
  assert.equal(submit.disabled, true);
  assert.equal(select.disabled, false, 'an explicit valid replacement remains available');
  const selectionStatus = held.renewal.querySelector('[data-client-renewal-selection-status]');
  assert.ok(selectionStatus, 'the missing-selection explanation must be outside the native option');
  assert.equal(selectionStatus.hidden, false);
  assert.match(selectionStatus.textContent, /no longer eligible.*Choose another eligible loan/);
  assert.equal(select.getAttribute('aria-describedby'), selectionStatus.getAttribute('id'));
  select.value = loanId; fire(select, 'change');
  assert.equal(submit.disabled, false);
  assert.equal(selectionStatus.hidden, true);
  assertSiblingDrafts(h, held);
  assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 0);
});

test('pending creation stays locked on selection changes and failed eligibility stays locked after verified save', async t => {
  let resolve;
  const h = await harness(t, {mutation:() => new Promise(done => resolve = done)});
  h.setLoans([{loan_id:loanId, eligible:true}, {loan_id:otherLoanId, eligible:true}]);
  await h.context.clientLoad('renewals', {refresh:true});
  const held = drafts(h);
  const select = held.renewal.querySelector('[name="loanId"]');
  const submit = held.renewal.querySelector('button[type="submit"]');
  select.value = loanId; fire(select, 'change');
  submit.disabled = false; fire(held.renewal, 'submit');
  await tick();
  select.value = otherLoanId; fire(select, 'change');
  assert.equal(submit.disabled, true, 'changing targets cannot unlock an in-flight creation');
  fire(held.renewal, 'submit');
  assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 1);
  h.failRead('/renewals');
  resolve({request:{request_id:requestId, client_id:clientId, loan_id:loanId, status:'pending',
    submitted_at:stamp, requested_amount:'5000.00', client_message:'Private renewal draft'}});
  await tick(); await tick();
  assert.equal(submit.disabled, true, 'busy cleanup cannot override failed eligibility');
  h.failRead(null);
  await h.context.clientLoad('renewals', {refresh:true});
  select.value = loanId; fire(select, 'change');
  assert.equal(submit.disabled, true, 'the saved original loan remains locked');
  select.value = otherLoanId; fire(select, 'change');
  assert.equal(submit.disabled, false, 'an explicit other eligible loan is available after completion');
  assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 1);
});

test('an old mount cleanup cannot clear replacement workspace drafts', async t => {
  const h = await harness(t);
  const old = drafts(h);
  const disposeOld = h.context.clientCleanup;
  await mountClientWorkspace(h.context);
  await tick();
  const replacement = h.root.querySelector('#client-support-form').querySelector('[name="message"]');
  replacement.value = 'Replacement workspace draft';
  disposeOld();
  assert.equal(old.support.querySelector('[name="message"]').value, '');
  assert.equal(replacement.value, 'Replacement workspace draft');
  assert.equal(replacement.disabled, false);
  assert.equal(h.root.querySelector('#client-support-form').querySelector('[name="message"]'), replacement);
});
