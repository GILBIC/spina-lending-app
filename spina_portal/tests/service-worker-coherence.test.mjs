import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../sw.js', import.meta.url), 'utf8');

function loadWorker({ cachedIndex = { source: 'cache' }, cachedAsset = null, networkIndex } = {}) {
  networkIndex ??= { source: 'network', ok: true };
  networkIndex.clone ??= () => networkIndex;
  const handlers = new Map();
  let fetchCalls = 0;
  const cacheWrites = [];
  const openedCaches = [];
  const context = {
    URL,
    Promise,
    Request: class Request {
      constructor(url, options = {}) {
        this.url = String(url);
        this.options = options;
      }
    },
    self: {
      location: { origin: 'https://spina.example' },
      addEventListener(type, handler) { handlers.set(type, handler); },
      skipWaiting() {},
      clients: { claim() {} },
    },
    caches: {
      open: async (name) => { openedCaches.push(name); return {
        addAll: async () => {},
        put: async (key, value) => { cacheWrites.push({ key, value }); },
        match: async (key) => key === '/index.html' ? cachedIndex : cachedAsset,
      }; },
      keys: async () => [],
      delete: async () => true,
      match: async (key) => key === '/index.html' ? cachedIndex : null,
    },
    fetch: async () => {
      fetchCalls += 1;
      return networkIndex;
    },
  };
  vm.runInNewContext(source, context, { filename: 'sw.js' });
  return { handlers, fetchCalls: () => fetchCalls, cacheWrites, openedCaches };
}

async function runNavigation(worker) {
  let responsePromise;
  worker.handlers.get('fetch')({
    request: {
      method: 'GET',
      url: 'https://spina.example/',
      mode: 'navigate',
    },
    respondWith(value) { responsePromise = Promise.resolve(value); },
  });
  return responsePromise;
}

test('navigation uses the active shell cache so HTML and modules stay on one version', async () => {
  const worker = loadWorker();
  const response = await runNavigation(worker);

  assert.deepEqual(response, { source: 'cache' });
  assert.equal(worker.fetchCalls(), 0);
});

test('navigation falls back to the network when no cached shell exists', async () => {
  const worker = loadWorker({ cachedIndex: null });
  const response = await runNavigation(worker);

  assert.equal(response.source, 'network');
  assert.equal(response.ok, true);
  assert.equal(worker.fetchCalls(), 1);
});

test('shell cache version advances when navigation strategy changes', () => {
  const version = Number(source.match(/spina-company-shell-v(\d+)/)[1]);
  assert.ok(version > 20, 'the released v20 shell must be replaced');
});

test('navigation reads only the active release cache', async () => {
  const worker = loadWorker();
  await runNavigation(worker);
  assert.equal(worker.openedCaches.length, 1);
  assert.equal(worker.openedCaches[0], source.match(/const CACHE_NAME = '([^']+)'/)[1]);
});

test('cached modules are not replaced in the background by a newer release', async () => {
  const worker = loadWorker({cachedAsset: {source: 'active-release-module'}});
  let responsePromise;
  worker.handlers.get('fetch')({
    request: {method: 'GET', url: 'https://spina.example/assets/app.js', mode: 'cors'},
    respondWith(value) { responsePromise = value; },
  });
  assert.equal((await responsePromise).source, 'active-release-module');
  assert.equal(worker.fetchCalls(), 0);
  assert.equal(worker.cacheWrites.length, 0);
});
