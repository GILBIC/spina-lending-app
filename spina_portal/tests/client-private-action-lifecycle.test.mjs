import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';

const flush = async () => {await setImmediate(); await setImmediate();};
const owner = 'synthetic-owner';
const note = {notification_id:'synthetic-note', recipient_user_id:owner, title:'Private update', is_read:false};
const account = {profile:{full_name:'Synthetic account'}, devices:[{id:'synthetic-device', status:'active', is_current:false}]};
const actions = [
  {name:'account', selector:'[data-client-revoke-device]', path:'/api/v1/account/devices/synthetic-device/revoke', result:{device:{id:'synthetic-device', status:'revoked'}}},
  {name:'updates', selector:'[data-client-notification-read]', path:'/api/v1/activity-notifications/synthetic-note/read', result:{...note, is_read:true}},
];

async function mount(t) {
  const prior = {document:globalThis.document, confirm:globalThis.confirm, setTimeout:globalThis.setTimeout};
  const toasts = [];
  globalThis.document = {getElementById:() => ({append:toast => toasts.push(toast.textContent)}), createElement:() => ({remove() {}})};
  globalThis.confirm = () => true;
  globalThis.setTimeout = () => ({unref() {}});
  t.after(() => Object.assign(globalThis, prior));
  const root = new Element(), controller = new AbortController(), calls = [];
  const query = root.querySelectorAll.bind(root);
  root.querySelectorAll = selector => {
    const pair = selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);
    return pair ? query(pair[1]).filter(node => node.getAttribute(pair[2].slice(1,-1)) !== null) : query(selector);
  };
  let resolve, reject, handle;
  const session = {user:{id:owner, role:'client'}, access_token:'original-token'};
  const context = {root, signal:controller.signal, session, getSession:() => session,
    setNavigation() {}, registerWorkspaceHandle:value => handle = value,
    api:{async request(path, options = {}) {
      calls.push({path, options});
      if (options.method) return new Promise((done, fail) => {resolve = done; reject = fail;});
      if (path === '/api/v1/account') return account;
      if (path === '/api/v1/client/loans') return {loans:[]};
      if (path === '/api/v1/activity-notifications') return [structuredClone(note)];
      if (path.startsWith('/api/v1/client/payment-proofs')) return {proofs:[], capability:{upload_available:true, max_bytes:10485760}};
      if (path === '/api/v1/client/payments') return {payments:[]};
      return {requests:[]};
    }}};
  await mountClientWorkspace(context);
  await handle.activate('client-payment-proofs');
  await flush();
  t.after(() => controller.abort());
  const support = root.querySelector('#client-support-form').querySelector('[name="message"]');
  const renewal = root.querySelector('#client-renewal-form').querySelector('[name="message"]');
  const file = root.querySelector('[name="proofFile"]');
  support.value = 'Private Support draft'; renewal.value = 'Private renewal draft'; file.value = 'synthetic.png';
  return {root, controller, context, session, calls, toasts, support, renewal, file,
    resolve:value => resolve(value), reject:status => reject(Object.assign(Error('Synthetic protected action failed'), {status}))};
}

for (const action of actions) for (const status of [401, 403]) {
  test(`${action.name} ${status} clears the current private mount and makes retained handlers inert`, async t => {
    const h = await mount(t), button = h.root.querySelector(action.selector);
    fire(button, 'click'); await flush();
    assert.deepEqual(h.calls.filter(call => call.options.method).map(call => [call.path, call.options]), [[action.path, {method:'POST'}]]);
    h.reject(status); await flush();
    assert.equal(h.root.innerHTML, '');
    for (const field of [h.support, h.renewal, h.file]) {assert.equal(field.value, ''); assert.equal(field.disabled, true);}
    assert.equal(button.disabled, true);
    button.disabled = false; fire(button, 'click'); await flush();
    assert.equal(h.calls.filter(call => call.options.method).length, 1);
    assert.deepEqual(h.toasts, []);
  });
}

for (const status of [401, 403]) test(`Updates ${status} still clears its current mount after the submitting row is replaced`, async t => {
  const h = await mount(t), button = h.root.querySelector('[data-client-notification-read]');
  fire(button, 'click'); await flush();
  await h.context.clientLoad('notifications', {refresh:true});
  button.isConnected = false;
  assert.notEqual(h.root.querySelector('[data-client-notification-read]'), button);
  h.reject(status); await flush();
  assert.equal(h.root.innerHTML, '', 'mount authority loss is independent of the old row connection');
  assert.equal(h.support.value, ''); assert.equal(h.file.value, '');
  assert.deepEqual(h.toasts, []);
});

for (const loss of ['abort', 'owner']) test(`late account success after ${loss} cannot toast, refresh or restore controls`, async t => {
  const h = await mount(t), button = h.root.querySelector('[data-client-revoke-device]');
  fire(button, 'click'); await flush();
  if (loss === 'abort') h.controller.abort(); else h.session.user.id = 'replacement-owner';
  const before = h.calls.length;
  h.resolve(actions[0].result); await flush();
  assert.equal(h.root.innerHTML, ''); assert.equal(button.disabled, true);
  assert.equal(h.support.value, ''); assert.equal(h.calls.length, before);
  assert.deepEqual(h.toasts, []);
});

for (const action of actions) {
  test(`late ${action.name} denial from a disposed mount cannot clear replacement content`, async t => {
    const h = await mount(t), button = h.root.querySelector(action.selector);
    fire(button, 'click'); await flush(); h.controller.abort();
    h.root.innerHTML = '<input name="replacement" />';
    const replacement = h.root.querySelector('[name="replacement"]'); replacement.value = 'New mount draft';
    h.reject(403); await flush();
    assert.equal(h.root.querySelector('[name="replacement"]'), replacement);
    assert.equal(replacement.value, 'New mount draft'); assert.equal(replacement.disabled, false);
    assert.deepEqual(h.toasts, []);
  });

  test(`${action.name} temporary failure retains private drafts and the exact action target`, async t => {
    const h = await mount(t), button = h.root.querySelector(action.selector);
    fire(button, 'click'); await flush(); h.reject(503); await flush();
    assert.equal(h.root.querySelector(action.selector), button);
    assert.equal(button.disabled, false); assert.equal(h.support.value, 'Private Support draft');
    assert.equal(h.renewal.value, 'Private renewal draft'); assert.equal(h.file.value, 'synthetic.png');
    assert.equal(h.calls.filter(call => call.options.method).length, 1);
  });

  test(`${action.name} same-owner token rotation preserves its successful local action`, async t => {
    const h = await mount(t), button = h.root.querySelector(action.selector);
    fire(button, 'click'); await flush(); h.session.access_token = 'rotated-token';
    h.resolve(action.result); await flush();
    assert.equal(h.support.value, 'Private Support draft'); assert.equal(h.file.value, 'synthetic.png');
    assert.equal(h.calls.filter(call => call.options.method).length, 1);
    assert.match(h.toasts.at(-1), action.name === 'account' ? /Device access revoked/ : /Update marked as read/);
    if (action.name === 'updates') assert.equal(button.hidden, true);
  });
}
