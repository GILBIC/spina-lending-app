import assert from 'node:assert/strict';
import test from 'node:test';

import { MemoryStorage, SessionStore } from '../assets/session.js';

const cryptoStub = { randomUUID: () => '11111111-2222-4333-8444-555555555555' };

test('session tokens stay in session storage while device identity persists locally', () => {
  const sessionStorageRef = new MemoryStorage();
  const localStorageRef = new MemoryStorage();
  const store = new SessionStore({ sessionStorageRef, localStorageRef, cryptoRef: cryptoStub });

  assert.equal(store.deviceId(), 'spina-web-11111111-2222-4333-8444-555555555555');
  store.save({
    access_token: 'access-token',
    refresh_token: 'refresh-token',
    expires_at: '2026-09-04T00:00:00Z',
    user: { id: 'user-1', role: 'Client', roles: ['client'], permissions: [] },
  });

  assert.equal(localStorageRef.getItem(SessionStore.DEVICE_KEY), 'spina-web-11111111-2222-4333-8444-555555555555');
  assert.equal(localStorageRef.getItem(SessionStore.SESSION_KEY), null);
  assert.match(sessionStorageRef.getItem(SessionStore.SESSION_KEY), /access-token/);
  assert.equal(store.load().user.role, 'Client');
});

test('clearing a session keeps the device identity and monotonic sequence', () => {
  const sessionStorageRef = new MemoryStorage();
  const localStorageRef = new MemoryStorage();
  const store = new SessionStore({ sessionStorageRef, localStorageRef, cryptoRef: cryptoStub });

  store.deviceId();
  assert.equal(store.nextDeviceSequence(), 1);
  assert.equal(store.nextDeviceSequence(), 2);
  store.save({ access_token: 'a', refresh_token: 'r', user: { id: 'u' } });
  store.clear();

  assert.equal(store.load(), null);
  assert.ok(store.deviceId().startsWith('spina-web-'));
  assert.equal(store.nextDeviceSequence(), 3);
});

test('invalid stored session data fails closed', () => {
  const sessionStorageRef = new MemoryStorage({ [SessionStore.SESSION_KEY]: '{bad-json' });
  const store = new SessionStore({
    sessionStorageRef,
    localStorageRef: new MemoryStorage(),
    cryptoRef: cryptoStub,
  });

  assert.equal(store.load(), null);
  assert.equal(sessionStorageRef.getItem(SessionStore.SESSION_KEY), null);
});
