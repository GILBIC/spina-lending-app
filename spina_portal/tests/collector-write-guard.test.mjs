import test from 'node:test';
import assert from 'node:assert/strict';
import { createCollectorWriteGuard } from '../assets/collector-write-guard.js';

function setup(online = true) {
  const target = new EventTarget();
  const controller = new AbortController();
  const messages = [];
  const guard = createCollectorWriteGuard({
    eventTarget: target, signal: controller.signal,
    isOnline: () => online, onLock: message => messages.push(message),
  });
  return {guard, target, controller, messages, setOnline(value) { online = value; target.dispatchEvent(new Event(value ? 'online' : 'offline')); }};
}

test('one collector write may be in flight across payment and remittance controls', () => {
  const {guard} = setup();
  assert.equal(guard.begin(), true);
  assert.equal(guard.begin(), false);
  guard.finish();
  assert.equal(guard.begin(), true);
  guard.dispose();
});

test('disconnect locks immediately and reconnect does not authorize a stale route', () => {
  const fixture = setup();
  fixture.setOnline(false);
  assert.equal(fixture.messages.length, 1);
  assert.equal(fixture.guard.begin(), false);
  fixture.setOnline(true);
  assert.equal(fixture.guard.begin(), false);
  assert.equal(fixture.guard.locked, true);
  fixture.guard.dispose();
  const refreshed = setup();
  assert.equal(refreshed.guard.begin(), true);
  refreshed.guard.dispose();
});

test('a missing offline event still blocks the submission at its point of use', () => {
  let online = true;
  const messages = [];
  const guard = createCollectorWriteGuard({eventTarget: new EventTarget(), isOnline: () => online, onLock: message => messages.push(message)});
  online = false;
  assert.equal(guard.begin(), false);
  assert.ok(messages.length > 0);
  guard.dispose();
});

test('initial offline mount and uncertain completion require a fresh mount', () => {
  const offline = setup(false);
  assert.equal(offline.guard.begin(), false);
  offline.guard.dispose();
  const uncertain = setup();
  assert.equal(uncertain.guard.begin(), true);
  uncertain.guard.lock('Check the saved result before another payment.');
  uncertain.guard.finish();
  assert.equal(uncertain.guard.begin(), false);
  assert.equal(uncertain.guard.locked, true);
  assert.ok(uncertain.messages.some(message => message.includes('saved result')));
  uncertain.guard.dispose();
});

test('disconnect during a request keeps controls locked after that request finishes', () => {
  const fixture = setup();
  assert.equal(fixture.guard.begin(), true);
  fixture.setOnline(false);
  fixture.setOnline(true);
  fixture.guard.finish();
  assert.equal(fixture.guard.begin(), false);
  fixture.guard.dispose();
});

test('logout/abort disposes listeners and late completions cannot authorize writes', () => {
  const fixture = setup();
  fixture.guard.begin();
  fixture.controller.abort();
  const count = fixture.messages.length;
  fixture.setOnline(false);
  fixture.guard.finish();
  fixture.guard.lock('Late response');
  assert.equal(fixture.messages.length, count);
  assert.equal(fixture.guard.current, false);
  assert.equal(fixture.guard.begin(), false);
});

test('a disconnected load re-applies its lock after the new markup is rendered', () => {
  const fixture = setup();
  fixture.setOnline(false);
  fixture.setOnline(true);
  const count = fixture.messages.length;
  fixture.guard.sync();
  assert.equal(fixture.messages.length, count + 1);
  assert.equal(fixture.guard.begin(), false);
  fixture.guard.dispose();
});
