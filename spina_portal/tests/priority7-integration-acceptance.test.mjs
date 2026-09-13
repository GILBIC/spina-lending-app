import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (url) => readFileSync(new URL(url, import.meta.url), 'utf8');

test('Priority #7 Management integration keeps Area Management and all verified read surfaces together', () => {
  const source = read('../assets/roles/management.js');

  assert.match(source, /mountAreaManagement/);
  assert.match(source, /management-area-management/);
  assert.match(source, /management-financial-statements\.js/);
  assert.match(source, /management-general-journal\.js/);
  assert.match(source, /management-loan-operations\.js/);
  assert.match(source, /management-past-due-report\.js/);
});

test('Priority #7 installed Web shell keeps verified Client and Management modules in one cache', () => {
  const source = read('../sw.js');

  for (const asset of [
    '/assets/client-schedule.js',
    '/assets/client-gcash.js',
    '/assets/client-statement.js',
    '/assets/management-financial-statements.js',
    '/assets/management-general-journal.js',
    '/assets/management-loan-operations.js',
    '/assets/management-past-due-report.js',
  ]) {
    assert.match(source, new RegExp(asset.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('Priority #7 Client schedule integration preserves unavailable handling and authoritative penalty payoff fields', () => {
  const source = read('../../gilbic_backend/src/gilbic_backend/client_loan_api.py');

  assert.match(source, /ClientLoanScheduleUnavailable/);
  assert.match(source, /status_code=409/);
  assert.match(source, /"penalty_status"/);
  assert.match(source, /"projected_penalty"/);
  assert.match(source, /"assessed_penalty_balance"/);
  assert.match(source, /"exact_payoff_total"/);
  assert.match(source, /"management_review_required_reason"/);
});
