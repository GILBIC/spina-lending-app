import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../sw.js', import.meta.url), 'utf8');

function loadWorker({ cachedIndex = { source: 'cache' }, networkIndex = { source: 'network', ok: true } } = {}) {
  const handlers = new Map();
  let fetchCalls = 0;
  const cacheWrites = [];
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
      open: async () => ({
        addAll: async () => {},
        put: async (key, value) => { cacheWrites.push({ key, value }); },
      }),
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
  return { handlers, fetchCalls: () => fetchCalls, cacheWrites };
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

  assert.deepEqual(response, { source: 'network', ok: true });
  assert.equal(worker.fetchCalls(), 1);
});

test('shell cache version advances when navigation strategy changes', () => {
  assert.match(source, /spina-company-shell-v20/);
});
