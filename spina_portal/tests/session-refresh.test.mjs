import assert from 'node:assert/strict';
import test from 'node:test';
import { SessionRefreshController } from '../assets/session-refresh.js';
import { SpinaApi } from '../assets/api.js';
import { SessionStore, MemoryStorage } from '../assets/session.js';

function setup() {
  let now = Date.parse('2026-09-29T00:00:00Z');
  const store = new SessionStore({ sessionStorageRef: new MemoryStorage(), localStorageRef: new MemoryStorage(), cryptoRef: { randomUUID: () => 'device' } });
  const alice = { access_token: 'alice', refresh_token: 'refresh', expires_at: '2026-09-29T00:05:00Z', user: { id: 'alice' } };
  store.save(alice);
  let complete; let calls = 0; let timer; const received = [];
  const api = new SpinaApi({ sessionStore: store, fetchImpl: () => { calls++; return new Promise((resolve) => complete = resolve); } });
  const controller = new SessionRefreshController({ api, sessionStore: store, now: () => now, setTimer: (fn, delay) => { timer = { fn: () => { timer = null; return fn(); }, delay }; return timer; }, clearTimer: () => { timer = null; }, onRefreshed: (value) => received.push(value), onExpired: () => received.push('expired') });
  return { store, alice, controller, received, calls: () => calls, timer: () => timer, setNow: (value) => now = value, complete: (status, data) => complete(new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } })) };
}

test('default browser timers retain the global receiver when starting and stopping refresh', (t) => {
  const originalSet = globalThis.setTimeout;
  const originalClear = globalThis.clearTimeout;
  t.after(() => { globalThis.setTimeout = originalSet; globalThis.clearTimeout = originalClear; });
  const scheduled = []; const cleared = [];
  globalThis.setTimeout = function (callback, delay) {
    if (this !== globalThis) throw new TypeError('Illegal invocation');
    scheduled.push({ callback, delay }); return scheduled.length;
  };
  globalThis.clearTimeout = function (timer) {
    if (this !== globalThis) throw new TypeError('Illegal invocation');
    cleared.push(timer);
  };
  const f = setup();
  const controller = new SessionRefreshController({ api: {}, sessionStore: f.store, now: () => Date.parse('2026-09-29T00:00:00Z') });
  controller.start();
  assert.equal(scheduled[0].delay, 180000);
  controller.start();
  assert.deepEqual(cleared, [1]);
  controller.stop();
  assert.deepEqual(cleared, [1, 2]);
  assert.equal(controller.timer, null);
});

test('refresh runs before expiry, persists new credentials, and schedules the next expiry', async () => {
  const f = setup(); f.controller.start();
  assert.equal(f.timer().delay, 180000);
  const work = f.timer().fn();
  f.complete(200, { ...f.alice, access_token: 'renewed', expires_at: '2026-09-29T01:00:00Z' });
  await work;
  assert.equal(f.store.load().access_token, 'renewed');
  assert.equal(f.received.length, 1);
  assert.equal(f.timer().delay, 3480000);
});

test('stopping refresh on logout prevents late UI callbacks and credentials restoration', async () => {
  const f = setup(); f.controller.start(); const work = f.timer().fn();
  f.store.clear(); f.controller.stop();
  f.complete(200, { ...f.alice, access_token: 'renewed' }); await work;
  assert.equal(f.store.load(), null); assert.deepEqual(f.received, []); assert.equal(f.timer(), null);
});

test('a temporary failure retries once later without replaying workspace writes', async () => {
  const f = setup(); f.controller.start(); const work = f.timer().fn();
  f.complete(503, { detail: 'Unavailable' }); await work;
  assert.equal(f.store.load().access_token, 'alice'); assert.equal(f.calls(), 1); assert.equal(f.timer().delay, 30000);
});

test('expired credentials are removed when refresh cannot be confirmed', async () => {
  const f = setup(); f.controller.start(); const work = f.timer().fn();
  f.setNow(Date.parse('2026-09-29T00:06:00Z')); f.complete(503, { detail: 'Unavailable' }); await work;
  assert.equal(f.store.load(), null); assert.deepEqual(f.received, ['expired']);
});

test('stalled refresh is bounded and its late response cannot install credentials', async () => {
  const f = setup(); let complete;
  const api = new SpinaApi({ sessionStore: f.store, refreshTimeoutMs: 10, fetchImpl: () => new Promise((resolve) => { complete = resolve; }) });
  await assert.rejects(api.refresh(), (error) => error.code === 'refresh_timeout');
  complete(new Response(JSON.stringify({ ...f.alice, access_token: 'too-late' }), { status: 200, headers: { 'content-type': 'application/json' } }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(f.store.load().access_token, 'alice');
});
