import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function text(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8');
}

test('portal shell includes login, Client registration, and accessible application roots', async () => {
  const html = await text('../index.html');

  assert.match(html, /id="login-form"/);
  assert.match(html, /id="registration-form"/);
  assert.match(html, /id="authenticated-app"/);
  assert.match(html, /id="role-navigation"/);
  assert.match(html, /id="role-content"/);
  assert.match(html, /aria-live="polite"/);
  for (const role of ['Client', 'Employee', 'Collector', 'Management']) {
    assert.match(html, new RegExp(role, 'i'));
  }
});

test('user-facing branding uses Spina only', async () => {
  const html = await text('../index.html');
  const config = await text('../assets/config.js');
  const manifest = JSON.parse(await text('../manifest.webmanifest'));

  assert.match(html, /<title>Spina<\/title>/);
  assert.match(html, />Spina</);
  assert.doesNotMatch(html, /SPINA Lending Company|SPINA Lending|>MVP</i);
  assert.doesNotMatch(config, /Controlled MVP/);
  assert.equal(manifest.name, 'Spina');
  assert.equal(manifest.short_name, 'Spina');
  assert.doesNotMatch(manifest.description, /SPINA Lending Company|SPINA Lending/);
});

test('PWA manifest is installable for browser and Windows app mode', async () => {
  const manifest = JSON.parse(await text('../manifest.webmanifest'));

  assert.equal(manifest.name, 'Spina');
  assert.equal(manifest.short_name, 'Spina');
  assert.equal(manifest.start_url, '/');
  assert.equal(manifest.display, 'standalone');
  assert.ok(Array.isArray(manifest.icons));
  assert.ok(manifest.icons.length >= 1);
});

test('service worker explicitly bypasses authenticated API and health traffic', async () => {
  const serviceWorker = await text('../sw.js');

  assert.match(serviceWorker, /pathname\.startsWith\('\/api\/'\)/);
  assert.match(serviceWorker, /pathname\.startsWith\('\/health\/'\)/);
  assert.match(serviceWorker, /request\.method !== 'GET'/);
  assert.match(serviceWorker, /event\.respondWith/);
});

test('application bootstrap mounts each canonical role workspace', async () => {
  const source = await text('../assets/app.js');

  assert.match(source, /mountClientWorkspace/);
  assert.match(source, /mountEmployeeWorkspace/);
  assert.match(source, /mountCollectorWorkspace/);
  assert.match(source, /mountManagementWorkspace/);
  assert.match(source, /normalizeRole/);
});
