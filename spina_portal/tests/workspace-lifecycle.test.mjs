import assert from 'node:assert/strict';
import test from 'node:test';
import {Element as ParsedElement} from './helpers/dom.mjs';
class ClientElement extends ParsedElement {
 constructor(){super();this.dataset={};this.classList={toggle(){}};}
 querySelectorAll(selector){const nodes=super.querySelectorAll(selector);for(const node of nodes){node.classList={toggle(){}};node.dataset={};}return nodes;}
}

import { MemoryStorage, SessionStore } from '../assets/session.js';

let instance = 0;
const tick = () => new Promise((resolve) => setImmediate(resolve));

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

class Element {
  constructor() {
    this.innerHTML = '';
    this.textContent = '';
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.listeners = new Map();
    this.classList = { toggle() {} };
  }
  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }
  emit(name) {
    return this.listeners.get(name)?.({ preventDefault() {}, target: this });
  }
  querySelector(selector) {
    if (selector === 'input[name="username"]') return { focus() {} };
    if (selector === '#management-loan-search') return new Element();
    if (selector === '[data-screen-panel]') return this.screenPanel ??= { open: false };
    return null;
  }
  querySelectorAll() { return []; }
  replaceChildren() { this.innerHTML = ''; }
  focus() {}
}

function json(payload) {
  return new Response(JSON.stringify(payload), {
    headers: { 'content-type': 'application/json' },
  });
}

async function harness(t, role, roles = [role]) {
  const elements = new Map();
  for (const id of [
    'auth-view', 'authenticated-app', 'role-content', 'role-navigation',
    'workspace-title', 'signed-in-role', 'signed-in-name', 'connection-status',
    'environment-label', 'refresh-workspace', 'logout-button', 'login-form',
    'workspace-choice', 'workspace-choice-label', 'screen-sharing-controls',
  ]) elements.set(id, role==='client'&&id==='role-content'?new ClientElement():new Element());
  const events = new EventTarget();
  const sessionStorage = new MemoryStorage();
  const localStorage = new MemoryStorage();
  const session = {
    access_token: 'synthetic-session', refresh_token: 'synthetic-refresh',
    user: { id: 'synthetic-user', role, roles, permissions: [], full_name: 'Office user' },
  };
  sessionStorage.setItem(SessionStore.SESSION_KEY, JSON.stringify(session));
  const accounts = [];
  const logoutResponse = deferred();
  const values = {
    document: {
      hidden: false,
      getElementById: (id) => elements.get(id) ?? null,
      addEventListener: events.addEventListener.bind(events),
      removeEventListener: events.removeEventListener.bind(events),
    },
    navigator: { onLine: true }, sessionStorage, localStorage,
    addEventListener: events.addEventListener.bind(events),
    dispatchEvent: events.dispatchEvent.bind(events),
    fetch: async (url) => {
      if (url.endsWith('/auth/me')) return json({ user: session.user });
      if (url.endsWith('/auth/logout')) return logoutResponse.promise;
      if (url.endsWith('/account')) {
        const result = deferred();
        accounts.push(result);
        return result.promise;
      }
      return json({});
    },
  };
  const previous = Object.fromEntries(Object.keys(values).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(values)) {
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  }
  t.after(() => {
    events.dispatchEvent(new Event('spina:unauthorized'));
    logoutResponse.resolve(json({}));
    for (const [key, descriptor] of Object.entries(previous)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  });
  await import(`../assets/app.js?lifecycle=${++instance}`);
  for (let count = 0; count < 30 && accounts.length === 0; count += 1) await tick();
  assert.equal(accounts.length, 1, 'boot must reach the real office workspace');
  return { elements, events, accounts, logoutResponse };
}

test('combined employee can switch workspace while old private response remains pending', async (t) => {
  const h = await harness(t, 'employee', ['employee', 'collector', 'employee_manager']);
  const picker = h.elements.get('workspace-choice');
  assert.equal(h.elements.get('workspace-choice-label').hidden, false);
  assert.match(picker.innerHTML, /value="collector"/);
  assert.doesNotMatch(picker.innerHTML, /management|employee_manager/);
  picker.value = 'collector';
  picker.emit('change');
  await tick();
  h.accounts[0].resolve(json({profile:{full_name:'Obsolete employee record'}}));
  await tick();
  assert.equal(h.elements.get('workspace-title').textContent, 'Collector workspace');
  assert.doesNotMatch(h.elements.get('role-content').innerHTML, /Obsolete employee record/);
  picker.value = 'management';
  picker.emit('change');
  assert.equal(h.elements.get('workspace-title').textContent, 'Collector workspace');
});

for (const role of ['employee', 'management', 'client']) {
  test(`${role}: starting logout immediately clears the workspace and ignores its pending response`, async (t) => {
    const h = await harness(t, role);
    const logout = h.elements.get('logout-button').emit('click');
    await tick();
    assert.equal(h.elements.get('role-content').innerHTML, '');
    h.accounts[0].resolve(json({ profile: { full_name: 'Late private account' } }));
    await tick();
    await tick();
    assert.equal(h.elements.get('role-content').innerHTML, '');
    h.logoutResponse.resolve(json({}));
    await logout;
    assert.equal(h.elements.get('authenticated-app').hidden, true);
  });

  test(`${role}: unauthorized event prevents late workspace data from returning`, async (t) => {
    const h = await harness(t, role);
    h.events.dispatchEvent(new Event('spina:unauthorized'));
    h.accounts[0].resolve(json({ profile: { full_name: 'Revoked private account' } }));
    await tick();
    await tick();
    assert.equal(h.elements.get('role-content').innerHTML, '');
    assert.equal(h.elements.get('role-navigation').innerHTML, '');
    assert.equal(h.elements.get('authenticated-app').hidden, true);
  });

  test(`${role}: a newer refresh cannot be overwritten by the older workspace response`, async (t) => {
    const h = await harness(t, role);
    const refresh = h.elements.get('refresh-workspace').emit('click');
    assert.equal(h.accounts.length, 2);
    h.accounts[1].resolve(json({ profile: { full_name: 'Current office account' } }));
    await refresh;
    if(role==='client')await tick();
    const current = h.elements.get('role-content').innerHTML;
    assert.match(current, /Current office account/);
    h.accounts[0].resolve(json({ profile: { full_name: 'Stale private account' } }));
    await tick();
    await tick();
    assert.equal(h.elements.get('role-content').innerHTML, current);
    assert.doesNotMatch(current, /Office intake reference/);
  });
}


test('Management membership opens one Web Management workspace without a role switch', async (t) => {
  const h = await harness(t, 'collector', ['collector', 'employee', 'management']);
  const picker = h.elements.get('workspace-choice');
  const label = h.elements.get('workspace-choice-label');
  assert.equal(h.elements.get('workspace-title').textContent, 'Management workspace');
  assert.equal(h.elements.get('signed-in-role').textContent, 'Management');
  assert.equal(label.hidden, true);
  assert.equal(picker.innerHTML, '');
  h.accounts[0].resolve(json({ profile: { full_name: 'Management user' } }));
  await tick();
  assert.equal(h.elements.get('workspace-title').textContent, 'Management workspace');
});
