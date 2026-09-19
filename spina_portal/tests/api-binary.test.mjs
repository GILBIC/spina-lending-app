import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, SpinaApi } from '../assets/api.js';

function harness(fetchImpl) {
  const h = { calls: [], session: { access_token: 'synthetic-token' }, clears: 0 };
  h.api = new SpinaApi({ sessionStore: {
    load: () => h.session, deviceId: () => 'synthetic-device', clear() { h.session = null; h.clears += 1; },
  }, async fetchImpl(path, options) { h.calls.push({ path, ...options }); return fetchImpl(path, options); } });
  return h;
}
test('raw evidence upload preserves exact bytes, media type, device authentication and abort signal', async () => {
  const rawBody = new Blob(['%PDF-1.7\nSynthetic signed document'], { type: 'application/pdf' });
  const controller = new AbortController();
  const h = harness(() => new Response(JSON.stringify({ evidence_id: 'synthetic' }), { headers: { 'content-type': 'application/json' } }));
  assert.deepEqual(await h.api.request('/protected/evidence', { method: 'POST', rawBody, headers: { 'Content-Type': rawBody.type }, signal: controller.signal }), { evidence_id: 'synthetic' });
  const request = h.calls[0];
  assert.equal(request.body, rawBody); assert.equal(request.headers['Content-Type'], 'application/pdf');
  assert.equal(request.headers.Authorization, 'Bearer synthetic-token'); assert.equal(request.headers['X-Device-Id'], 'synthetic-device');
  assert.equal(request.signal, controller.signal); assert.equal(request.cache, 'no-store');
  assert.doesNotMatch(request.path, /token|Bearer/);
});
test('JSON and raw body ambiguity is rejected without issuing a request', async () => {
  const h = harness(() => { throw new Error('should not fetch'); });
  await assert.rejects(h.api.request('/protected/evidence', { method: 'POST', body: {}, rawBody: new Blob(['x']) }), TypeError);
  assert.deepEqual(h.calls, []);
});
test('protected binary download returns exact bytes and keeps credentials out of the URL', async () => {
  const bytes = new Uint8Array([0, 255, 14, 0, 128]);
  const h = harness(() => new Response(bytes, { headers: { 'content-type': 'application/pdf' } }));
  const result = await h.api.request('/protected/document', { responseType: 'blob' });
  assert.ok(result instanceof Blob); assert.deepEqual(new Uint8Array(await result.arrayBuffer()), bytes);
  assert.equal(result.type, 'application/pdf'); assert.equal(h.calls[0].path, '/protected/document');
  assert.equal(h.calls[0].headers.Authorization, 'Bearer synthetic-token');
});
for (const status of [401, 403, 409, 503]) test(`binary request still exposes structured ${status} errors and 401 clears session`, async () => {
  const h = harness(() => new Response(JSON.stringify({ detail: 'Synthetic download failure' }), { status, headers: { 'content-type': 'application/json' } }));
  await assert.rejects(h.api.request('/protected/document', { responseType: 'blob' }), (error) => {
    assert.ok(error instanceof ApiError); assert.equal(error.status, status); assert.equal(error.message, 'Synthetic download failure'); return true;
  });
  assert.equal(h.clears, status === 401 ? 1 : 0); assert.equal(h.calls.length, 1);
});
test('raw upload uncertainty never retries and is distinguishable from a failed download', async () => {
  const h = harness(() => { throw new TypeError('Synthetic network loss'); });
  await assert.rejects(h.api.request('/protected/evidence', { method: 'POST', rawBody: new Blob(['x']) }), { code: 'network_uncertain' });
  await assert.rejects(h.api.request('/protected/document', { responseType: 'blob' }), { code: 'network_unavailable' });
  assert.equal(h.calls.length, 2);
});
test('logged out raw and binary requests stop before fetching', async () => {
  const h = harness(() => { throw new Error('should not fetch'); }); h.session = null;
  await assert.rejects(h.api.request('/protected/evidence', { method: 'POST', rawBody: new Blob(['x']) }), { status: 401 });
  await assert.rejects(h.api.request('/protected/document', { responseType: 'blob' }), { status: 401 });
  assert.deepEqual(h.calls, []);
});
