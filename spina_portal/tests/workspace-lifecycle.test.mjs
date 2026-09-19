import assert from 'node:assert/strict';
import test from 'node:test';
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
    return null;
  }
  querySelectorAll() { return []; }
  focus() {}
}

function json(payload) {
  return new Response(JSON.stringify(payload), {
    headers: { 'content-type': 'application/json' },
  });
}

async function harness(t, role) {
  const elements = new Map();
  for (const id of [
    'auth-view', 'authenticated-app', 'role-content', 'role-navigation',
    'workspace-title', 'signed-in-role', 'signed-in-name', 'connection-status',
    'environment-label', 'refresh-workspace', 'logout-button', 'login-form',
  ]) elements.set(id, new Element());
  const events = new EventTarget();
  const sessionStorage = new MemoryStorage();
  const localStorage = new MemoryStorage();
  const session = {
    access_token: 'synthetic-session', refresh_token: 'synthetic-refresh',
    user: { id: 'synthetic-user', role, roles: [role], permissions: [], full_name: 'Office user' },
  };
  sessionStorage.setItem(SessionStore.SESSION_KEY, JSON.stringify(session));
  const accounts = [];
  const logoutResponse = deferred();
  const values = {
    document: { getElementById: (id) => elements.get(id) ?? null },
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
    const current = h.elements.get('role-content').innerHTML;
    assert.match(current, /Current office account/);
    h.accounts[0].resolve(json({ profile: { full_name: 'Stale private account' } }));
    await tick();
    await tick();
    assert.equal(h.elements.get('role-content').innerHTML, current);
    assert.doesNotMatch(current, /Office intake reference/);
  });
}
