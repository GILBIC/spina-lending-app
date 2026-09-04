import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function text(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8');
}

const forbiddenLongBrand = /spina lending(?: company)?/i;

test('public sign-in uses Spina Lending Company while installed product remains Spina', async () => {
  const html = await text('../index.html');
  const manifest = JSON.parse(await text('../manifest.webmanifest'));

  assert.match(html, /<title>Spina Lending Company<\/title>/);
  assert.match(html, /<h1>Spina Lending Company<\/h1>/);
  assert.match(html, /<strong>Spina<\/strong>/);
  assert.equal(manifest.name, 'Spina');
  assert.equal(manifest.short_name, 'Spina');
  assert.equal(forbiddenLongBrand.test(JSON.stringify(manifest)), false);
});

test('Windows install surface and build metadata use Spina without a lending suffix', async () => {
  const files = await Promise.all([
    text('../../spina_pc/install_spina_pc.ps1'),
    text('../../spina_pc/uninstall_spina_pc.ps1'),
    text('../../spina_pc/README.md'),
    text('../../tools/build_portal.mjs'),
  ]);
  const combined = files.join('\n');

  assert.match(files[0], /\$ShortcutName = "Spina\.lnk"/);
  assert.match(files[3], /application: 'Spina'/);
  assert.equal(forbiddenLongBrand.test(combined), false);
});
