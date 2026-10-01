import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../assets/app.css', import.meta.url), 'utf8');
const client = readFileSync(new URL('../assets/roles/client.js', import.meta.url), 'utf8');

test('Web shell keeps the warmer SPINA visual hierarchy without shrinking touch targets', () => {
  assert.match(css, /--surface-soft:\s*#fcf8fa/);
  assert.match(css, /--line:\s*#eadde4/);
  assert.match(css, /--radius:\s*16px/);
  assert.match(css, /--radius-lg:\s*24px/);
  assert.match(css, /body\s*\{[^}]*radial-gradient/s);
  assert.match(css, /\.button\s*\{[^}]*min-height:\s*48px/s);
  assert.match(css, /\.button-primary\s*\{[^}]*linear-gradient/s);
});

test('Client-facing copy prioritizes borrower questions instead of internal system wording', () => {
  assert.doesNotMatch(client, /protected SPINA server/i);
  assert.doesNotMatch(client, /obligations are always shown separately/i);
  assert.match(client, /balance, amount due, and schedule/i);
  assert.match(client, /official loan and payment history/i);
});

test('Client operational payment table becomes stacked cards on small screens', () => {
  assert.match(client, /class="mobile-card-table client-payment-table"/);
  assert.match(client, /data-label="Date"/);
  assert.match(client, /data-label="Amount"/);
  assert.match(css, /@media \(max-width: 680px\)[\s\S]*\.mobile-card-table/s);
  assert.match(css, /\.mobile-card-table td::before/);
});
