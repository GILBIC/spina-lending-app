import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {runInNewContext} from 'node:vm';

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
