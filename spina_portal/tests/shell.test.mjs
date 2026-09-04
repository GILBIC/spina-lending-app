import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function text(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8');
}

test('portal shell is a single Spina Lending Company sign-in surface', async () => {
  const html = await text('../index.html');
  const app = await text('../assets/app.js');

  assert.match(html, /<title>Spina Lending Company<\/title>/);
  assert.match(html, />Spina Lending Company</);
  assert.match(html, /id="login-form"/);
  assert.match(html, /<button[^>]*type="submit"[^>]*>Sign in<\/button>/);
  assert.match(html, /id="authenticated-app"/);
  assert.match(html, /id="role-navigation"/);
  assert.match(html, /id="role-content"/);
  assert.match(html, /aria-live="polite"/);

  assert.doesNotMatch(html, /id="registration-form"/);
  assert.doesNotMatch(html, /Request an account/i);
  assert.doesNotMatch(html, /Send registration request/i);
  assert.doesNotMatch(html, /One secure workspace for every role/i);
  assert.doesNotMatch(
    html,
    /Client, Employee, Collector, and Management use the same protected Spina backend and official records/i,
  );
  assert.doesNotMatch(html, /class="role-strip"/);
  assert.doesNotMatch(html, /Collector phones may require Management device approval/i);
  assert.doesNotMatch(html, /Sign in securely/i);
  assert.doesNotMatch(app, /registration-form/);
});

test('user-facing branding avoids legacy MVP wording', async () => {
  const html = await text('../index.html');
  const config = await text('../assets/config.js');

  assert.match(html, /Spina Lending Company/);
  assert.doesNotMatch(html, />MVP</i);
  assert.doesNotMatch(config, /Controlled MVP/);
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

test('service worker refreshes the shell when Management device administration is added', async () => {
  const serviceWorker = await text('../sw.js');

  assert.match(serviceWorker, /spina-company-shell-v3/);
  assert.match(serviceWorker, /'\/assets\/management-devices\.js'/);
  assert.match(serviceWorker, /'\/assets\/roles\/management\.js'/);
});

test('application bootstrap mounts each canonical role workspace', async () => {
  const source = await text('../assets/app.js');

  assert.match(source, /mountClientWorkspace/);
  assert.match(source, /mountEmployeeWorkspace/);
  assert.match(source, /mountCollectorWorkspace/);
  assert.match(source, /mountManagementWorkspace/);
  assert.match(source, /normalizeRole/);
});
