import assert from 'node:assert/strict';
import test from 'node:test';
import { formatMoney, formatDateTime } from '../assets/ui.js';
process.env.TZ = 'UTC';

test('shared money rendering preserves every authoritative cent, including signed numeric(18,2)', () => {
  for (const [value, expected] of [
    ['1234567890123456.78', '₱1,234,567,890,123,456.78'],
    ['9999999999999999.99', '₱9,999,999,999,999,999.99'],
    ['-90071992547409.93', '-₱90,071,992,547,409.93'],
    ['0', '₱0.00'], ['1.2', '₱1.20'], [null, '—'],
  ]) assert.equal(formatMoney(value), expected);
});

test('business instants always display Philippine time, including the next business day', () => {
  assert.equal(formatDateTime('2026-09-29T17:00:00Z'), 'Sep 30, 2026, 1:00 AM');
});
