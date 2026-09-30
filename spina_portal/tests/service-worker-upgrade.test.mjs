import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {runInNewContext} from 'node:vm';

test('a fresh worker serves the complete static app graph offline without caching protected APIs', async () => {
  const origin = 'https://spina.test';
  const listeners = new Map();
  const stores = new Map([['spina-company-shell-v17', new Map()]]);
  class ShellRequest extends Request {
    constructor(input, options) {
      super(input instanceof Request ? input : new URL(input, origin), options);
    }
  }
  const caches = {
    async open(name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name);
      return {
        async addAll(inputs) {
          for (const input of inputs) {
            const request = new ShellRequest(input);
            const pathname = new URL(request.url).pathname;
            const file = pathname === '/' ? '../index.html' : `..${pathname}`;
            store.set(request.url, new Response(await readFile(new URL(file, import.meta.url))));
          }
        },
        async put(input, response) { store.set(new ShellRequest(input).url, response); },
      };
    },
    async keys() { return [...stores.keys()]; },
    async delete(name) { return stores.delete(name); },
    async match(input) {
      const url = new ShellRequest(input).url;
      for (const store of stores.values()) {
        if (store.has(url)) return store.get(url).clone();
      }
    },
  };
  runInNewContext(await readFile(new URL('../sw.js', import.meta.url), 'utf8'), {
    URL, Request: ShellRequest, caches,
    fetch: async () => { throw new Error('offline'); },
    self: {location: {origin}, addEventListener: (name, listener) => listeners.set(name, listener),
      skipWaiting() {}, clients: {claim() {}}},
  });
  for (const name of ['install', 'activate']) {
    let job;
    listeners.get(name)({waitUntil(promise) { job = promise; }});
    await job;
  }
  assert.equal(stores.has('spina-company-shell-v17'), false);
  async function offlineFetch(pathname) {
    let job;
    listeners.get('fetch')({request: new Request(origin + pathname), respondWith(promise) { job = promise; }});
    return job ? await job : undefined;
  }
  const seen = new Set();
  async function visit(pathname) {
    if (seen.has(pathname)) return;
    seen.add(pathname);
    const response = await offlineFetch(pathname);
    assert.ok(response instanceof Response, `${pathname} must load on first offline reload`);
    for (const match of (await response.text()).matchAll(/\bfrom\s+['"]([^'"]+)['"]/g)) {
      if (match[1].startsWith('.')) await visit(new URL(match[1], origin + pathname).pathname);
    }
  }
  assert.ok((await offlineFetch('/index.html')) instanceof Response);
  await visit('/assets/app.js');
  assert.ok(seen.size > 40, 'walk the complete current app graph');
  assert.equal(await offlineFetch('/api/v1/auth/me'), undefined);
  assert.equal(await caches.match('/api/v1/auth/me'), undefined);
});

test('shell upgrade replaces a fresh HTTP-cached module and serves it offline', async () => {
  const origin = 'https://spina.test';
  const asset = `${origin}/assets/roles/collector.js`;
  const oldBody = 'previous Collector module';
  const newBody = 'current Collector module';
  const cachesByName = new Map([['spina-company-shell-v13', new Map([[asset, oldBody]])]]);
  const listeners = new Map();
  const pending = [];
  class ShellRequest extends Request {
    constructor(input, options) {
      super(input instanceof Request ? input : new URL(input, origin), options);
    }
  }
  const caches = {
    async open(name) {
      if (!cachesByName.has(name)) cachesByName.set(name, new Map());
      const contents = cachesByName.get(name);
      return {
        async addAll(inputs) {
          for (const input of inputs) {
            const request = new ShellRequest(input);
            // Model the fresh one-hour HTTP response demonstrated in the real
            // browser upgrade probe: ordinary requests reuse the old module.
            const body = request.url === asset && request.cache !== 'reload' ? oldBody : newBody;
            contents.set(request.url, body);
          }
        },
        async put(input, response) {
          contents.set(new ShellRequest(input).url, await response.text());
        },
      };
    },
    async keys() { return [...cachesByName.keys()]; },
    async delete(name) { return cachesByName.delete(name); },
    async match(input) {
      const url = new ShellRequest(input).url;
      for (const contents of cachesByName.values()) {
        if (contents.has(url)) return new Response(contents.get(url));
      }
    },
  };
  runInNewContext(await readFile(new URL('../sw.js', import.meta.url), 'utf8'), {
    URL, Request:ShellRequest, caches,
    fetch:async () => { throw new TypeError('Synthetic offline state'); },
    self:{location:{origin}, addEventListener:(name, listener) => listeners.set(name, listener),
      skipWaiting() {}, clients:{claim() {}}},
  });
  listeners.get('install')({waitUntil:promise => pending.push(promise)});
  await Promise.all(pending);
  listeners.get('activate')({waitUntil:promise => pending.push(promise)});
  await Promise.all(pending);
  assert.equal(cachesByName.has('spina-company-shell-v13'), false, 'Retire the previous shell after successful installation');
  let response;
  listeners.get('fetch')({request:new Request(asset), respondWith:promise => { response = promise; }});
  assert.equal(await (await response).text(), newBody);
});
