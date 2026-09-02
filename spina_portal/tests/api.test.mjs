import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, SpinaApi } from '../assets/api.js';
import { MemoryStorage, SessionStore } from '../assets/session.js';

const DEVICE_ID = 'spina-web-11111111-2222-4333-8444-555555555555';
const cryptoStub = { randomUUID: () => '11111111-2222-4333-8444-555555555555' };

function createStore() {
  return new SessionStore({
    sessionStorageRef: new MemoryStorage(),
    localStorageRef: new MemoryStorage(),
    cryptoRef: cryptoStub,
  });
}

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

test('successful login sends web device context and stores only the returned session', async () => {
  const store = createStore();
  const requests = [];
  const api = new SpinaApi({
    apiBaseUrl: 'https://api.example',
    appVersion: '0.1.0',
    sessionStore: store,
    fetchImpl: async (url, init) => {
      requests.push({ url, init });
      return jsonResponse(200, {
        success: true,
        data: {
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          expires_at: '2026-09-04T00:00:00Z',
          user: {
            id: 'collector-1',
            username: 'collector.one',
            full_name: 'Collector One',
            role: 'Collector',
            roles: ['collector'],
            permissions: ['route.view', 'collection.create'],
          },
          permissions: ['route.view', 'collection.create'],
        },
      });
    },
  });

  const session = await api.login('collector.one', 'correct-password');

  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, 'https://api.example/api/v1/auth/login');
  assert.equal(requests[0].init.method, 'POST');
  assert.deepEqual(JSON.parse(requests[0].init.body), {
    username: 'collector.one',
    password: 'correct-password',
    device_id: DEVICE_ID,
    platform: 'web',
    app_version: '0.1.0',
  });
  assert.equal(session.access_token, 'access-token');
  assert.equal(store.load().user.role, 'Collector');
});

test('device approval denial never leaves a browser session behind', async () => {
  const store = createStore();
  const api = new SpinaApi({
    apiBaseUrl: '',
    appVersion: '0.1.0',
    sessionStore: store,
    fetchImpl: async () =>
      jsonResponse(403, {
        success: false,
        error: {
          code: 'device_approval_required',
          message: 'Management approval is required for this device.',
        },
      }),
  });

  await assert.rejects(
    () => api.login('collector.one', 'password'),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 403);
      assert.equal(error.code, 'device_approval_required');
      return true;
    },
  );
  assert.equal(store.load(), null);
});

test('authenticated requests attach bearer and device headers', async () => {
  const store = createStore();
  store.deviceId();
  store.save({
    access_token: 'access-token',
    refresh_token: 'refresh-token',
    user: { id: 'client-1', role: 'Client', roles: ['client'], permissions: [] },
  });
  let captured;
  const api = new SpinaApi({
    apiBaseUrl: '',
    appVersion: '0.1.0',
    sessionStore: store,
    fetchImpl: async (_url, init) => {
      captured = init;
      return jsonResponse(200, { success: true, data: { ok: true } });
    },
  });

  const data = await api.request('/api/v1/account');

  assert.deepEqual(data, { ok: true });
  assert.equal(captured.headers.Authorization, 'Bearer access-token');
  assert.equal(captured.headers['X-Device-Id'], DEVICE_ID);
  assert.equal(captured.headers['X-App-Platform'], 'web');
  assert.equal(captured.headers['X-App-Version'], '0.1.0');
});

test('a Collector financial POST is attempted once and network uncertainty is explicit', async () => {
  const store = createStore();
  store.deviceId();
  store.save({
    access_token: 'access-token',
    refresh_token: 'refresh-token',
    user: { id: 'collector-1', role: 'Collector', roles: ['collector'], permissions: ['collection.create'] },
  });
  let calls = 0;
  const api = new SpinaApi({
    apiBaseUrl: '',
    appVersion: '0.1.0',
    sessionStore: store,
    fetchImpl: async () => {
      calls += 1;
      throw new TypeError('connection closed after send');
    },
  });

  await assert.rejects(
    () =>
      api.request('/api/v1/collector/collections', {
        method: 'POST',
        body: { client_transaction_id: 'tx-1' },
        financial: true,
      }),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.code, 'network_uncertain');
      assert.equal(error.status, 0);
      return true;
    },
  );
  assert.equal(calls, 1);
  assert.equal(store.load().access_token, 'access-token');
});
