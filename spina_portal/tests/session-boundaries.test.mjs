import assert from 'node:assert/strict';
import test from 'node:test';
import { SpinaApi } from '../assets/api.js';
import { SessionStore, MemoryStorage } from '../assets/session.js';

const session = (name) => ({ access_token: `${name}-access`, refresh_token: `${name}-refresh`, user: { id: name, role: 'Employee' } });
function fixture() {
  const store = new SessionStore({ sessionStorageRef: new MemoryStorage(), localStorageRef: new MemoryStorage(), cryptoRef: { randomUUID: () => 'test-device' } });
  store.save(session('alice'));
  let complete;
  let request;
  const api = new SpinaApi({ sessionStore: store, logoutTimeoutMs: 10, fetchImpl: (_url, init) => { request = init; return new Promise((resolve) => { complete = resolve; }); } });
  return { api, store, request: () => request, complete: (status, data) => complete(new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } })) };
}

test('an old authenticated 401 cannot clear the next account', async () => {
  const f = fixture();
  const response = f.api.request('/api/v1/account');
  f.store.clear(); f.store.save(session('bob'));
  f.complete(401, { detail: 'Expired' });
  await assert.rejects(response);
  assert.equal(f.store.load().user.id, 'bob');
});

for (const status of [200, 401, 403]) {
  test(`late refresh ${status} cannot restore or clear a replacement session`, async () => {
    const f = fixture();
    const response = f.api.refresh();
    f.store.clear(); f.store.save(session('bob'));
    f.complete(status, status === 200 ? session('alice-new') : { detail: 'Denied' });
    await assert.rejects(response);
    assert.equal(f.store.load().user.id, 'bob');
  });
}

test('sign-out removes local credentials immediately and bounds remote revocation', async () => {
  const f = fixture();
  const logout = f.api.logout();
  assert.equal(f.store.load(), null);
  assert.equal(f.request().headers.Authorization, 'Bearer alice-access');
  f.store.save(session('bob'));
  await logout;
  assert.equal(f.store.load().user.id, 'bob');
});

test('a late login cannot restore a session after local sign-out', async () => {
  const f = fixture();
  const login = f.api.login('alice', 'synthetic');
  await f.api.logout();
  f.complete(200, session('alice'));
  await assert.rejects(login);
  assert.equal(f.store.load(), null);
});
